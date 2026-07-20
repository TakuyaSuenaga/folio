# 編集部フロー規定 (FLOW.md)

この雑誌はAI編集部が毎日発行する。各役職はスキルとして `.claude/skills/` に定義され、**工程ごとに独立したClaude呼び出し**として実行される。この文書は全役職が従う憲法である。要点はリポジトリの CLAUDE.md にも転記しておくこと。

## 編集部の原則

1. **別プロセス原則(フレッシュアイズ)**: 各工程は独立した呼び出しで実行し、前工程の思考コンテキストを持ち込まない。書いた者は校閲・校正をしない。これは品質の生命線であり、工程を1セッションに統合してはならない。
2. **機械にできることをLLMにさせない**: アフィリエイトリンク加工・原稿一致チェック・リンク死活確認・発行処理は決定論スクリプトで行う。LLMはこれらを代行しない。
3. **実在チェーン**: 誌面に載る作品・店は、必ずリサーチがAPIから取得した `cand_id` を持つ。チェーンの切れたitemは誌面に載らない。
4. **issues/ には校了済みのみ**: ゲラは `desk/` に置く。校了判定だけが発行を許す。
5. **落丁より休刊**: 品質が確保できない日は休刊する。休刊はvol番号を消費しない(欠番を作らない)。
6. **desk/ は全てコミットする**: 企画書・候補・校閲レポートを含む編集のログは資産である(将来のコンテンツ候補)。

## 工程と受け渡し

作業ディレクトリ: `desk/vol-{NNN}/`

| # | 工程 | 担当(スキル) | 入力 | 出力 |
|---|------|--------------|------|------|
| 1 | 企画 | editor-in-chief(企画モード) | 台帳・申し送り・起点シード | `01_kikaku.json` |
| 2 | リサーチ | researcher | 01 | `02_kouho.json` |
| 3 | 執筆 | genre-editor | 01, 02 | `03_genko.json` |
| 4 | 校閲 | koetsu | 01, 02, 03 | `04_koetsu.json` |
| 4b | 改稿 | genre-editor(改稿モード) | 03, 04 | 03を更新 ※fix_required時のみ・1回 |
| 5 | リンク加工 | **スクリプト** | 03 | `05_goudata.json` |
| 6 | 組版 | art-director | 05 | `gera.html` |
| 7 | 校正 | kousei | 05, gera | `06_kousei.json` |
| 8 | 校了 | editor-in-chief(校了モード) | 01〜06, gera | `07_kouryou.json` |
| 8b | 責了対応 | art-director(修正モード) | 07 | geraを更新 ※責了時のみ・1回 |
| 9 | 発行 | **スクリプト** | gera, 07 | `issues/vol-{NNN}.html`・台帳追記・index更新 |

**ループ上限**: 4bは1回、8bは1回。それでも解決しない場合は休刊とし、GitHub Issueに理由を起票して当日を終了する。

## 起点シード

企画モードには毎日、機械が用意したシードを渡す: 日付・曜日・今日の記念日・季節、可能なら天気やフィード見出し。編集長のテーマがモード崩壊(情緒的テーマへの収束)しないための外部ノイズである。

## 永続ファイル

- `editorial/daicho.md` — 特集台帳。校了ごとに発行スクリプトが1行追記。企画モードは**全行読む**
- `editorial/moushiokuri.md` — 申し送り。校了モードが書き、翌日の企画モードが読む。直近14日分を残す
- `editorial/FLOW.md` — 本書
- `.claude/skills/` — 各役職

## リンク加工スクリプト(工程5)の仕様

決定論の変換のみ行う: 03の各linkについて、ドメイン→アフィリエイトパラメータ付与の対応表を適用し、`sponsored: true/false` を確定して05を出力する。対応表にないドメインはそのまま `sponsored: false`。LLMは介在しない。

## 表記規定(全役職共通・校正が照合)

- 本文の数字は漢数字(西暦・数量とも)。DATA欄・ノンブル・日付・型番は算用数字
- ダッシュは「——」(2倍)、三点リーダは「……」(2倍)
- 作品名は『』、引用・強調は「」。単位は半角
- 敬体禁止(である調)。感嘆符・疑問符は原則使わない

## JSONスキーマ

各スキルが自分の入出力スキーマを持つ。ここには全体の型だけ示す。

```
01_kikaku.json   … vol, date, title, thesis, kigen_card, genres[{genre, order, hacchu}], lead_draft, spot_color?, kinshi[]
02_kouho.json    … vol, genres[{genre, candidates[{cand_id, source_api, source_id, title, creator, year, publisher, meta, links[], verify, researcher_note}]}], ng[]
03_genko.json    … issue{vol, date, title, lead}, items[{genre, cand_id, sentei_riyu, title, creator, year, publisher?, meta?, essay, links[]}], colophon?{note}
04_koetsu.json   … vol, verdict, shiteki[{id, target, severity, type, quote, problem, fix}]
05_goudata.json  … 03と同形 + 各linkにsponsored確定(=ADの入力)
06_kousei.json   … vol, machine{...}, shiteki[{id, location, severity, type, genzai, teisei}]
07_kouryou.json  … vol, hantei(校了|責了|休刊), lead_final, sekiryo_shiji[], daicho_line, moushiokuri, riyu
```

## GitHub Actions への写像

1工程=1ステップ=1回の `claude -p`(またはclaude-code-action)呼び出し。プロンプトは最小でよい(例: 「vol.024の校閲をして」)——スキルのdescriptionが工程を引き受ける。4b/8bは前工程の出力JSONの判定フィールドで条件分岐する。工程5と9は通常のrun stepでスクリプトを実行する。
