# folio

AI編集部が毎日発行するWeb雑誌。毎日 JST 0:00 に GitHub Actions が編集部パイプライン(企画→リサーチ→執筆→校閲→組版→校正→校了→発行)を実行し、校了した号だけを GitHub Pages で公開する。

- 誌面: `issues/`(GitHub Pages で公開)
- 制作過程: `desk/`(全コミット。公開サイトには含まれない)
- 編集部の憲法: `editorial/FLOW.md`
- 設計書: `docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md`

## セットアップ(初回のみ・手動)

### 1. Secrets(Settings → Secrets and variables → Actions)

| Secret | 用途 | 必須 |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | claude-code-action 認証。`claude setup-token` で発行 | ✔ |
| `RAKUTEN_APP_ID` | 楽天ブックスAPI(book/poetry/photo/architecture) | ✔ |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Spotify API(music) | ✔ |
| `TMDB_API_KEY` | TMDB(film) | ✔ |
| `GOOGLE_PLACES_API_KEY` | Google Places(cafe/restaurant) | ✔ |
| `RAKUTEN_AFF_PARAM` | 楽天アフィリエイトID。`key=value` 形式 | 任意 |

### 2. GitHub Pages

Settings → Pages → Source を **GitHub Actions** にする。

### 3. 初回公開

Actions タブ → `deploy-pages` → Run workflow。vol.001 / vol.002 と表紙が公開される。

### 4. リハーサル

Actions タブ → `daily-issue` → Run workflow で1号ぶん手動実行できる。
以降は毎日 JST 0:00(UTC 15:00)に自動実行される(GitHub の cron は数分〜数十分遅れることがある)。

## 開発

```bash
pip install pytest pytest-cov
python -m pytest tests/ -v --cov=scripts --cov-report=term-missing
```
