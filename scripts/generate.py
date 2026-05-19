#!/usr/bin/env python3
"""Daily news generator: fetches weather and news, outputs index.html"""

import os
import sys
from datetime import datetime, timezone, timedelta
from html import escape

import requests

JST = timezone(timedelta(hours=9))

ICON_MAP = {
    "01d": "☀️", "01n": "☀️",
    "02d": "🌤️", "02n": "🌤️",
    "03d": "☁️", "03n": "☁️", "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️", "10d": "🌧️", "10n": "🌧️",
    "11d": "⛈️", "11n": "⛈️",
    "13d": "❄️", "13n": "❄️",
    "50d": "🌫️", "50n": "🌫️",
}

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def fetch_weather(api_key: str, city: str) -> dict:
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": api_key, "lang": "ja", "units": "metric"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def fetch_news(api_key: str, country: str, language: str, size: int = 10) -> list:
    r = requests.get(
        "https://newsdata.io/api/1/news",
        params={"apikey": api_key, "country": country, "language": language, "size": size},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def truncate(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    return text[:max_len] + "…" if len(text) > max_len else text


def render_html(weather: dict, articles: list, city: str, now: datetime) -> str:
    desc = weather["weather"][0]["description"]
    temp = weather["main"]["temp"]
    feels = weather["main"]["feels_like"]
    humidity = weather["main"]["humidity"]
    wind = weather["wind"]["speed"]
    emoji = ICON_MAP.get(weather["weather"][0]["icon"], "🌡️")

    weekday = WEEKDAYS[now.weekday()]
    date_str = now.strftime(f"%Y年%m月%d日（{weekday}）")
    updated = now.strftime("%Y-%m-%d %H:%M JST")

    news_items = ""
    for a in articles:
        title = escape(a.get("title") or "")
        description = escape(truncate(a.get("description") or ""))
        source = escape(a.get("source_name") or "")
        link = a.get("link") or "#"
        desc_html = f'<p class="desc">{description}</p>' if description else ""
        news_items += f"""
      <article class="card">
        <h3><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
        {desc_html}
        <span class="tag">{source}</span>
      </article>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{date_str} 天気・ニュース</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: #f4f4f5; color: #18181b; line-height: 1.6; }}
    a {{ color: inherit; }}

    .header {{ background: #fff; border-bottom: 1px solid #e4e4e7; padding: 14px 20px; }}
    .header h1 {{ font-size: 1rem; font-weight: 600; color: #52525b; }}
    .header h1 strong {{ color: #18181b; }}

    .main {{ max-width: 720px; margin: 20px auto; padding: 0 16px 48px; }}

    .weather {{ background: #fef9c3; border: 1px solid #fde047; border-radius: 12px; padding: 18px 20px; margin-bottom: 24px; }}
    .weather-label {{ font-size: 0.75rem; font-weight: 700; color: #854d0e; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }}
    .weather-row {{ display: flex; align-items: center; gap: 12px; }}
    .weather-emoji {{ font-size: 2.4rem; line-height: 1; }}
    .weather-temp {{ font-size: 1.9rem; font-weight: 800; color: #713f12; }}
    .weather-desc {{ font-size: 0.9rem; color: #92400e; margin-top: 2px; }}
    .weather-meta {{ display: flex; gap: 16px; margin-top: 10px; font-size: 0.82rem; color: #78350f; }}

    .section-head {{ font-size: 0.8rem; font-weight: 700; color: #71717a; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }}

    .card {{ background: #fff; border-radius: 8px; border: 1px solid #e4e4e7; padding: 14px 16px; margin-bottom: 10px; }}
    .card h3 {{ font-size: 0.92rem; font-weight: 600; line-height: 1.5; }}
    .card h3 a {{ text-decoration: none; color: #18181b; }}
    .card h3 a:hover {{ color: #2563eb; text-decoration: underline; }}
    .card .desc {{ font-size: 0.8rem; color: #71717a; margin-top: 5px; }}
    .card .tag {{ display: inline-block; margin-top: 8px; font-size: 0.72rem; color: #a1a1aa; background: #f4f4f5; padding: 2px 8px; border-radius: 99px; }}

    .footer {{ text-align: center; padding: 20px; font-size: 0.75rem; color: #a1a1aa; }}
    .footer a {{ color: #a1a1aa; text-decoration: none; }}
    .footer a:hover {{ text-decoration: underline; }}
  </style>
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

    <div class="section-head">📰 今日のニュース</div>
    {news_items}
  </main>
  <footer class="footer">
    <p>データ取得元: <a href="https://openweathermap.org" target="_blank">OpenWeather</a> / <a href="https://newsdata.io" target="_blank">NewsData.io</a></p>
    <p>最終更新: {updated}</p>
  </footer>
</body>
</html>
"""


def main():
    ow_key = os.environ.get("OPENWEATHER_API_KEY", "")
    city = os.environ.get("OPENWEATHER_CITY", "Nagoya")
    nd_key = os.environ.get("NEWSDATA_API_KEY", "")
    country = os.environ.get("NEWSDATA_COUNTRY", "jp")
    language = os.environ.get("NEWSDATA_LANGUAGE", "ja")

    if not ow_key or not nd_key:
        print("ERROR: OPENWEATHER_API_KEY and NEWSDATA_API_KEY must be set", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(JST)
    print(f"Fetching data for {now.strftime('%Y-%m-%d %H:%M JST')} ...")

    weather = fetch_weather(ow_key, city)
    print(f"  Weather: {weather['weather'][0]['description']}, {weather['main']['temp']}°C")

    articles = fetch_news(nd_key, country, language)
    print(f"  News: {len(articles)} articles")

    html = render_html(weather, articles, city, now)
    out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Generated {out}")


if __name__ == "__main__":
    main()
