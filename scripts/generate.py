#!/usr/bin/env python3
"""Daily news site generator — weather + 5 categorized sections."""

import os
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from html import escape

import feedparser
import requests

NOTION_WORKS_PAGE_ID = "364f1c78ada280b19e09ec1bdf9361cf"

JST = timezone(timedelta(hours=9))
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
ICON_MAP = {
    "01d": "☀️", "01n": "☀️", "02d": "🌤️", "02n": "🌤️",
    "03d": "☁️", "03n": "☁️", "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️", "10d": "🌧️", "10n": "🌧️",
    "11d": "⛈️", "11n": "⛈️", "13d": "❄️", "13n": "❄️",
    "50d": "🌫️", "50n": "🌫️",
}

def _gnews_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"

# --------------------------------------------------------------------------- #
# Section definitions
# type "simple"      : single API call, flat list of cards
# type "multi"       : multiple API calls merged, deduped by link
# type "subsections" : one sub-group per game title (required items)
#
# Each item/subsection may have:
#   rss_query       : Google News RSS search query (merged with API results)
#   rss_size        : max items to take from RSS (default 3)
#   filter_keywords : post-fetch keyword filter on title+description
# --------------------------------------------------------------------------- #
SECTIONS = [
    {
        "title": "🏠 国内ニュース",
        "color": "#22c55e", "text": "#166534", "bg": "#f0fdf4",
        "type": "simple",
        "params": {"country": "jp", "language": "ja", "category": "domestic", "size": 5},
    },
    {
        "title": "🌍 国際・経済ニュース",
        "color": "#3b82f6", "text": "#1e40af", "bg": "#eff6ff",
        "type": "simple",
        "params": {"language": "ja", "category": "world,business", "size": 5},
    },
    {
        "title": "🎮 ゲームニュース",
        "color": "#a855f7", "text": "#6b21a8", "bg": "#faf5ff",
        "type": "multi",
        "items": [
            {"params": {"language": "ja", "q": "ゲーム 新作 発表", "size": 4},
             "rss_query": "ゲーム 新作 発表", "rss_size": 2},
            {"params": {"language": "ja", "q": "NIKKE 勝利の女神", "size": 3},
             "required_label": "勝利の女神NIKKE",
             "rss_query": "NIKKE 勝利の女神", "rss_size": 3,
             "filter_keywords": ["NIKKE", "ニッケ", "勝利の女神"]},
        ],
    },
    {
        "title": "🃏 カードゲームニュース",
        "color": "#ec4899", "text": "#9d174d", "bg": "#fdf2f8",
        "type": "subsections",
        "subsections": [
            {"label": "遊戯王",
             "params": {"language": "ja", "q": "遊戯王", "size": 5},
             "rss_query": "遊戯王 カードゲーム OCG", "rss_size": 3,
             "filter_keywords": ["遊戯王"]},
            {"label": "ユニオンアリーナ",
             "params": {"language": "ja", "q": "ユニオンアリーナ", "size": 5},
             "rss_query": "ユニオンアリーナ", "rss_size": 3,
             "filter_keywords": ["ユニオンアリーナ"]},
            {"label": "ホロライブカードゲーム",
             "params": {"language": "ja", "q": "ホロライブ カードゲーム", "size": 5},
             "rss_query": "ホロライブ カードゲーム OCG", "rss_size": 3,
             "filter_keywords": ["ホロライブ"]},
        ],
    },
    {
        "title": "💻 IT・テクノロジーニュース",
        "color": "#f97316", "text": "#9a3412", "bg": "#fff7ed",
        "type": "simple",
        "params": {"language": "ja", "category": "technology", "size": 5},
    },
]


# --------------------------------------------------------------------------- #
# Fetch helpers
# --------------------------------------------------------------------------- #
def fetch_news(api_key: str, params: dict) -> list:
    try:
        r = requests.get(
            "https://newsdata.io/api/1/news",
            params={"apikey": api_key, **params},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"    [warn] newsdata fetch failed: {e}", file=sys.stderr)
        return []


def fetch_rss(query: str, size: int = 3) -> list:
    """Fetch articles from Google News RSS and normalize to newsdata format."""
    try:
        url = _gnews_url(query)
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:size]:
            articles.append({
                "title": entry.get("title", ""),
                "description": entry.get("summary", ""),
                "link": entry.get("link", "#"),
                "source_name": entry.get("source", {}).get("title", "Google News"),
            })
        return articles
    except Exception as e:
        print(f"    [warn] rss fetch failed: {e}", file=sys.stderr)
        return []


def merge_articles(primary: list, secondary: list) -> list:
    """Merge two article lists, deduped by link. Primary comes first."""
    seen: set = set()
    result = []
    for a in primary + secondary:
        link = a.get("link") or ""
        if link and link not in seen:
            seen.add(link)
            result.append(a)
    return result


def keyword_filter(articles: list, keywords: list) -> list:
    if not keywords:
        return articles
    return [
        a for a in articles
        if any(kw in (a.get("title") or "") or kw in (a.get("description") or "")
               for kw in keywords)
    ]


def fetch_works(notion_key: str) -> dict:
    """Fetch schedule and todo items from the Notion Works page."""
    try:
        r = requests.get(
            f"https://api.notion.com/v1/blocks/{NOTION_WORKS_PAGE_ID}/children",
            headers={"Authorization": f"Bearer {notion_key}", "Notion-Version": "2022-06-28"},
            timeout=15,
        )
        r.raise_for_status()
        blocks = r.json().get("results", [])

        schedule, todos = [], []
        section = None
        for b in blocks:
            btype = b.get("type")
            content = b.get(btype, {})
            rich = content.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich)

            if btype == "heading_2":
                if "予定" in text:
                    section = "schedule"
                elif "課題" in text:
                    section = "todo"
                else:
                    section = None
            elif btype == "bulleted_list_item" and section == "schedule":
                schedule.append(text)
            elif btype == "to_do" and section == "todo":
                todos.append({
                    "id": b.get("id", ""),
                    "text": text,
                    "checked": content.get("checked", False),
                })

        return {"schedule": schedule, "todos": todos}
    except Exception as e:
        print(f"    [warn] notion fetch failed: {e}", file=sys.stderr)
        return {"schedule": [], "todos": []}


def fetch_weather(api_key: str, city: str) -> dict:
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": api_key, "lang": "ja", "units": "metric"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------- #
# HTML renderers
# --------------------------------------------------------------------------- #
def truncate(text: str, n: int = 80) -> str:
    return text[:n] + "…" if text and len(text) > n else (text or "")


def render_card(article: dict) -> str:
    title = escape(article.get("title") or "")
    desc = escape(truncate(article.get("description") or ""))
    source = escape(article.get("source_name") or "")
    link = article.get("link") or "#"
    desc_p = f'<p class="desc">{desc}</p>' if desc else ""
    return (
        f'<article class="card">'
        f'<h3><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></h3>'
        f'{desc_p}'
        f'<span class="tag">{source}</span>'
        f'</article>'
    )


def render_works(works: dict, proxy_url: str = "") -> str:
    schedule_items = "".join(
        f'<li class="works-item">{escape(s)}</li>'
        for s in works["schedule"]
    ) or '<li class="works-empty">予定なし</li>'

    todo_items = "".join(
        f'<li class="works-item{"  works-done" if t["checked"] else ""}" data-block-id="{t["id"]}">'
        f'<label class="works-check-label">'
        f'<input type="checkbox" class="todo-checkbox"{"  checked" if t["checked"] else ""} data-block-id="{t["id"]}" />'
        f'<span>{escape(t["text"])}</span>'
        f'</label>'
        f'</li>'
        for t in works["todos"]
    ) or '<li class="works-empty">課題なし</li>'

    proxy_script = f'<script>const NOTION_PROXY = "{proxy_url}";</script>' if proxy_url else ""

    return f"""<section class="news-section works-section">
  <div class="section-head" style="border-left:4px solid #6366f1;background:#eef2ff">
    <h2 style="color:#3730a3">📌 Works</h2>
  </div>
  <div class="works-body">
    <div class="works-col">
      <div class="works-label" style="color:#3730a3;border-left:3px solid #6366f1">📅 予定一覧</div>
      <ul class="works-list">{schedule_items}</ul>
    </div>
    <div class="works-col">
      <div class="works-label" style="color:#3730a3;border-left:3px solid #6366f1">📋 課題</div>
      <ul class="works-list">{todo_items}</ul>
    </div>
  </div>
</section>
{proxy_script}"""


def render_empty(label: str) -> str:
    return f'<article class="card card-empty">本日の{escape(label)}情報なし</article>'


def render_section(section: dict, api_key: str) -> str:
    c, t, bg = section["color"], section["text"], section["bg"]
    title = section["title"]
    stype = section["type"]

    header = (
        f'<div class="section-head" style="border-left:4px solid {c};background:{bg}">'
        f'<h2 style="color:{t}">{title}</h2>'
        f'</div>'
    )

    if stype == "simple":
        articles = fetch_news(api_key, section["params"])
        inner = "".join(render_card(a) for a in articles) if articles else render_empty(title)
        body = f'<div class="cards">{inner}</div>'

    elif stype == "multi":
        seen: set = set()
        cards_html: list[str] = []
        for item in section["items"]:
            api_articles = fetch_news(api_key, item["params"])
            rss_query = item.get("rss_query")
            rss_articles = fetch_rss(rss_query, item.get("rss_size", 3)) if rss_query else []
            articles = merge_articles(rss_articles, api_articles)
            articles = keyword_filter(articles, item.get("filter_keywords", []))
            fresh = [a for a in articles if a.get("link") not in seen]
            for a in fresh:
                seen.add(a.get("link"))
            label = item.get("required_label")
            if label and not fresh:
                cards_html.append(render_empty(label))
            else:
                cards_html.extend(render_card(a) for a in fresh)
        body = f'<div class="cards">{"".join(cards_html)}</div>'

    elif stype == "subsections":
        subs: list[str] = []
        for sub in section["subsections"]:
            api_articles = fetch_news(api_key, sub["params"])
            rss_query = sub.get("rss_query")
            rss_articles = fetch_rss(rss_query, sub.get("rss_size", 3)) if rss_query else []
            articles = merge_articles(rss_articles, api_articles)
            articles = keyword_filter(articles, sub.get("filter_keywords", []))
            # Show up to 3 cards per subsection
            articles = articles[:3]
            cards = "".join(render_card(a) for a in articles) if articles else render_empty(sub["label"])
            subs.append(
                f'<div class="subsection">'
                f'<div class="sub-label" style="color:{t};border-left:3px solid {c}">{sub["label"]}</div>'
                f'<div class="cards">{cards}</div>'
                f'</div>'
            )
        body = f'<div class="subsections">{"".join(subs)}</div>'

    else:
        body = ""

    return f'<section class="news-section">{header}{body}</section>'


# --------------------------------------------------------------------------- #
# Full page
# --------------------------------------------------------------------------- #
def render_page(weather: dict, sections_html: list, city: str, now: datetime, ow_key: str = "") -> str:
    emoji = ICON_MAP.get(weather["weather"][0]["icon"], "🌡️")
    desc = weather["weather"][0]["description"]
    temp = weather["main"]["temp"]
    feels = weather["main"]["feels_like"]
    humidity = weather["main"]["humidity"]
    wind = weather["wind"]["speed"]

    weekday = WEEKDAYS[now.weekday()]
    date_str = now.strftime(f"%Y年%m月%d日（{weekday}）")
    updated = now.strftime("%Y-%m-%d %H:%M JST")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{date_str} 天気・ニュース</title>
  <link rel="stylesheet" href="style.css" />
  <link rel="manifest" href="manifest.json" />
  <meta name="theme-color" content="#ffffff" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-title" content="デイリーニュース" />
  <link rel="apple-touch-icon" href="icons/icon-192.png" />
  <script>
    if ('serviceWorker' in navigator) {{
      window.addEventListener('load', () => {{
        navigator.serviceWorker.register('service-worker.js');
      }});
    }}
  </script>
</head>
<body>
  <header class="header">
    <h1>📰 <strong>{date_str}</strong> 天気・ニュース</h1>
  </header>
  <main class="main">

    <div class="weather">
      <div class="weather-label">{emoji} {city}の天気</div>
      <div class="weather-row">
        <span class="weather-emoji">{emoji}</span>
        <div>
          <div class="weather-temp">{temp:.1f}°C</div>
          <div class="weather-desc">{desc}（体感 {feels:.1f}°C）</div>
        </div>
      </div>
      <div class="weather-meta">
        <span>💧 湿度 {humidity}%</span>
        <span>🌬️ 風速 {wind} m/s</span>
      </div>
    </div>

    {"".join(sections_html)}

  </main>
  <script>
    // ページ読み込み時に天気をリアルタイム取得
    (async function() {{
      const ICON_MAP = {{
        '01d':'☀️','01n':'☀️','02d':'🌤️','02n':'🌤️',
        '03d':'☁️','03n':'☁️','04d':'☁️','04n':'☁️',
        '09d':'🌧️','09n':'🌧️','10d':'🌧️','10n':'🌧️',
        '11d':'⛈️','11n':'⛈️','13d':'❄️','13n':'❄️',
        '50d':'🌫️','50n':'🌫️',
      }};
      try {{
        const res = await fetch(
          'https://api.openweathermap.org/data/2.5/weather'
          + '?q={city}&appid={ow_key}&lang=ja&units=metric'
        );
        if (!res.ok) return;
        const d = await res.json();
        const emoji = ICON_MAP[d.weather[0].icon] || '🌡️';
        document.querySelector('.weather-label').textContent = emoji + ' ' + d.name + 'の天気';
        document.querySelector('.weather-emoji').textContent = emoji;
        document.querySelector('.weather-temp').textContent = d.main.temp.toFixed(1) + '°C';
        document.querySelector('.weather-desc').textContent =
          d.weather[0].description + '（体感 ' + d.main.feels_like.toFixed(1) + '°C）';
        const meta = document.querySelectorAll('.weather-meta span');
        if (meta[0]) meta[0].textContent = '💧 湿度 ' + d.main.humidity + '%';
        if (meta[1]) meta[1].textContent = '🌬️ 風速 ' + d.wind.speed + ' m/s';
      }} catch(e) {{}}
    }})();

    document.querySelectorAll('.todo-checkbox').forEach(function(cb) {{
      cb.addEventListener('change', async function() {{
        if (!window.NOTION_PROXY) return;
        const blockId = cb.dataset.blockId;
        const checked = cb.checked;
        const item = cb.closest('.works-item');
        item.classList.toggle('works-done', checked);
        cb.disabled = true;
        try {{
          await fetch(NOTION_PROXY + '/' + blockId, {{
            method: 'PATCH',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ to_do: {{ checked }} }}),
          }});
        }} catch(e) {{
          cb.checked = !checked;
          item.classList.toggle('works-done', !checked);
        }} finally {{
          cb.disabled = false;
        }}
      }});
    }});
  </script>
  <footer class="footer">
    <p>データ取得元:
      <a href="https://openweathermap.org" target="_blank">OpenWeather</a> /
      <a href="https://newsdata.io" target="_blank">NewsData.io</a> /
      <a href="https://news.google.com" target="_blank">Google News</a>
    </p>
    <p>最終更新: {updated}</p>
  </footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    ow_key = os.environ.get("OPENWEATHER_API_KEY", "")
    city = os.environ.get("OPENWEATHER_CITY", "Nagoya")
    nd_key = os.environ.get("NEWSDATA_API_KEY", "")
    notion_key = os.environ.get("NOTION_API_KEY", "")

    if not ow_key or not nd_key:
        print("ERROR: OPENWEATHER_API_KEY and NEWSDATA_API_KEY must be set", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(JST)
    print(f"Generating for {now.strftime('%Y-%m-%d %H:%M JST')} ...")

    weather = fetch_weather(ow_key, city)
    print(f"  Weather: {weather['weather'][0]['description']}, {weather['main']['temp']}°C")

    sections_html = []

    if notion_key:
        print("  Section: 📌 Works")
        works = fetch_works(notion_key)
        proxy_url = os.environ.get("NOTION_PROXY_URL", "")
        sections_html.append(render_works(works, proxy_url))

    for section in SECTIONS:
        print(f"  Section: {section['title']}")
        sections_html.append(render_section(section, nd_key))

    html = render_page(weather, sections_html, city, now, ow_key=ow_key)
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
