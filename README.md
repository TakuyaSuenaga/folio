# folio

AI編集部が毎日発行するWeb雑誌。毎日 JST 0:00 に GitHub Actions が編集部パイプライン(企画→リサーチ→執筆→校閲→組版→校正→校了→発行)を実行し、校了した号だけを GitHub Pages で公開する。

- 誌面: `issues/`(GitHub Pages で公開)
- 制作過程: `desk/`(全コミット。公開サイトには含まれない)
- 編集部の憲法: `editorial/FLOW.md`
- 設計書: `docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md`

## 開発

```bash
pip install pytest pytest-cov
python -m pytest tests/ -v --cov=scripts --cov-report=term-missing
```
