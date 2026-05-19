# daily-news-site

名古屋の天気と最新ニュースを毎朝自動取得して表示するシンプルな静的サイト。

## 仕組み

```
GitHub Actions (毎朝 7:00 JST)
  │
  ├─ OpenWeather API → 名古屋の天気
  ├─ NewsData.io API → 最新ニュース 10件
  │
  └─ index.html を生成 → main ブランチにコミット
                              │
                         GitHub Pages で配信
```

## セットアップ

### 1. GitHub Secrets の設定

`Settings > Secrets and variables > Actions` から以下を追加:

| Secret 名 | 値の例 |
|-----------|--------|
| `OPENWEATHER_API_KEY` | `ba411cb0...` |
| `OPENWEATHER_CITY` | `Nagoya` |
| `NEWSDATA_API_KEY` | `pub_93c903...` |
| `NEWSDATA_COUNTRY` | `jp` |
| `NEWSDATA_LANGUAGE` | `ja` |

### 2. GitHub Pages の有効化

`Settings > Pages > Source` を以下に設定:
- **Source**: Deploy from a branch
- **Branch**: `main` / `(root)`

### 3. 初回 or 手動更新

`Actions > Update Daily News > Run workflow` で即時実行できます。

## ローカル実行

```bash
pip install requests
export OPENWEATHER_API_KEY=xxx
export OPENWEATHER_CITY=Nagoya
export NEWSDATA_API_KEY=xxx
export NEWSDATA_COUNTRY=jp
export NEWSDATA_LANGUAGE=ja
python scripts/generate.py
open index.html
```
