# folio — AI編集部による日刊Web雑誌

このリポジトリはAI編集部が毎日1号のWeb雑誌を発行する。憲法は `editorial/FLOW.md` であり、本書はその要点の転記である。矛盾があればFLOW.mdに従う。

## 原則

1. **別プロセス原則(フレッシュアイズ)**: 各工程は独立したClaude呼び出しで実行する。書いた者は校閲・校正をしない。工程を1セッションに統合しない
2. **機械にできることをLLMにさせない**: リンク加工・原稿一致チェック・リンク死活・発行は `scripts/` の決定論スクリプトで行う
3. **実在チェーン**: 誌面に載る作品・店は必ずリサーチがAPIから取得した `cand_id` を持つ
4. **issues/ には校了済みのみ**: ゲラは `desk/` に置く
5. **落丁より休刊**: 品質が確保できない日は休刊する。休刊はvol番号を消費しない
6. **desk/ は全てコミットする**: 編集ログは資産である

## 工程(担当スキルは .claude/skills/)

| # | 工程 | 担当 | 出力 |
|---|------|------|------|
| 1 | 企画 | editor-in-chief | desk/vol-NNN/01_kikaku.json |
| 2 | リサーチ | researcher | 02_kouho.json |
| 3 | 執筆 | genre-editor | 03_genko.json |
| 4 | 校閲 | koetsu | 04_koetsu.json |
| 4b | 改稿(fix_required時のみ・1回) | genre-editor | 03を更新 |
| 5 | リンク加工 | scripts/link_decorator.py | 05_goudata.json |
| 6 | 組版 | art-director | gera.html |
| 7 | 校正 | scripts/kousei_machine.py + kousei | 06_kousei.json |
| 8 | 校了 | editor-in-chief | 07_kouryou.json |
| 8b | 責了対応(責了時のみ・1回) | art-director | geraを更新 |
| 9 | 発行 | scripts/publish.py | issues/vol-NNN.html・台帳追記・index再生成 |

## 表記規定(校正が照合)

- 本文の数字は漢数字(西暦・数量とも)。DATA欄・ノンブル・日付・型番は算用数字
- ダッシュは「——」(2倍)、三点リーダは「……」(2倍)
- 作品名は『』、引用・強調は「」。単位は半角
- 敬体禁止(である調)。感嘆符・疑問符は原則使わない

## 開発

- スクリプトは Python 3.12・標準ライブラリのみ・決定論(LLM を介在させない)
- テスト: `python -m pytest tests/ -v`(カバレッジ 80% 以上)
- 日次パイプライン: `.github/workflows/daily-issue.yml`(JST 0:00)。手動リハーサルは workflow_dispatch
