# folio — AI編集部による日刊Web雑誌 設計書

日付: 2026-07-19
ステータス: 承認済み

## 概要

folio は AI 編集部が毎日発行する Web 雑誌である。GitHub Actions が毎日 JST 0:00(cron `0 15 * * *` UTC)に編集部パイプラインを実行し、校了した号だけを GitHub Pages で公開する。編集部の憲法は `editorial/FLOW.md`(docs/EditorialDepartment2/FLOW.md を正本として移設)であり、本設計はそれを GitHub リポジトリ上に実装する。

## 決定事項(ブレインストーミング結果)

| 項目 | 決定 |
|---|---|
| ホスティング | GitHub Pages(actions/deploy-pages 方式で `issues/` のみ公開) |
| 技術スタック | 生 HTML 継続。React/Next.js/Tailwind は不採用 |
| Claude 認証 | `CLAUDE_CODE_OAUTH_TOKEN`(サブスクリプションの OAuth トークン) |
| モデル | 全工程 `claude-haiku-4-5-20251001` |
| 外部 API | 楽天ブックス / openBD / Spotify / TMDB / Google Places — 全キー取得済み前提 |
| 既存 vol.001/002 | 正式発行として公開アーカイブに載せ、台帳を引き継ぐ。自動発行は vol.003 から |
| 実行時刻 | JST 0:00(GitHub cron の遅延数分〜数十分は許容) |

### 生 HTML を選んだ理由(React/Next.js 不採用の根拠)

1. 校正の機械チェック(`kousei_machine.py`)は最終 HTML への原稿完全一致・`<script>` 不在・リンク照合を検証する。ビルドステップを挟むと決定論チェックが壊れる
2. art-director は号ごとに扉組み・段組・特色を意図的に変える(AD NOTE に前号との差分を記録する文化)。共通コンポーネント化はこの思想と衝突する
3. 無人の日次 cron 運用では「ビルド失敗」という故障モードが存在しないことが重要
4. 自己完結 HTML は依存の腐敗がなく、アーカイブとして永続する

## リポジトリ構成

```
folio/
├── CLAUDE.md                      # FLOW.md の要点を転記(全工程が読む)
├── editorial/
│   ├── FLOW.md                    # 正本(docs/EditorialDepartment2 から移設)
│   ├── daicho.md                  # 特集台帳。vol.001/002 の 2 行を引き継ぐ
│   └── moushiokuri.md             # 申し送り(vol.002 のものを引き継ぐ)
├── .claude/skills/                # 編集部 6 役職(docs からコピー、内容改変なし)
│   ├── editor-in-chief/SKILL.md   # docs/EditorialDepartment1/SKILL.md
│   ├── researcher/SKILL.md        # docs/EditorialDepartment2/SKILL.md(最新版)
│   ├── genre-editor/SKILL.md      # docs/EditorialDepartment1/mnt/.../genre-editor/
│   ├── koetsu/SKILL.md            # docs/EditorialDepartment1/mnt/.../koetsu/
│   ├── kousei/SKILL.md            # docs/EditorialDepartment1/mnt/.../kousei/
│   └── art-director/SKILL.md      # docs/.../art-director/(264 行版。現在の空ファイルを上書き)
├── scripts/                       # 決定論スクリプト(Python 3.12・標準ライブラリのみ)
│   ├── seed.py
│   ├── verify_links.py
│   ├── link_decorator.py
│   ├── kousei_machine.py
│   └── publish.py
├── tests/                         # pytest(フィクスチャは vol.002 実データ)
├── desk/                          # 制作過程。結果に関わらず全コミット
│   └── vol-{NNN}/
├── issues/                        # 公開ルート(Pages が配信するのはここだけ)
│   ├── index.html                 # 表紙兼アーカイブ。publish.py が台帳から再生成
│   ├── vol-001.html
│   └── vol-002.html
└── .github/workflows/
    ├── daily-issue.yml            # 毎日 15:00 UTC
    └── test.yml                   # PR/push で pytest
```

Pages のディレクトリ指定制約(`/` か `/docs` のみ)を回避するため、branch 配信ではなく **actions/deploy-pages で `issues/` をアーティファクトとしてデプロイ**する。`desk/` の制作ログはリポジトリに残るが公開されない。

## GitHub Actions: daily-issue.yml

トリガー: `schedule`(`0 15 * * *`)+ `workflow_dispatch`。`concurrency` で二重実行防止。ジョブ全体 `timeout-minutes: 45`。

FLOW.md の写像どおり **1 工程 = 1 ステップ = 1 回の claude-code-action 呼び出し**。プロンプトは最小(例: 「vol.024 の校閲をして」)で、スキルの description が工程を引き受ける。

| # | ステップ | 実行主体 | 出力 |
|---|---|---|---|
| 1 | checkout + Python セットアップ | actions | — |
| 2 | 号数決定+シード生成 | `seed.py` | vol 番号(台帳最終行 +1)、シードテキスト |
| 3 | 企画 | claude(editor-in-chief) | `01_kikaku.json` |
| 4 | リサーチ | claude(researcher)+ API キー env | `02_kouho.json` |
| 5 | 執筆 | claude(genre-editor) | `03_genko.json` |
| 6 | 校閲 | claude(koetsu) | `04_koetsu.json` |
| 7 | 改稿(条件付) | claude(genre-editor 改稿モード) | 03 更新。04 の verdict=fix_required 時のみ・1 回 |
| 8 | リンク加工 | `link_decorator.py` | `05_goudata.json` |
| 9 | 組版 | claude(art-director) | `gera.html` |
| 10 | 校正 | `kousei_machine.py`(URL 実測 ON)→ claude(kousei) | `06_kousei.json` |
| 11 | 校了 | claude(editor-in-chief 校了モード) | `07_kouryou.json` |
| 12 | 責了対応(条件付) | claude(art-director 修正モード) | gera 更新。hantei=責了 時のみ・1 回 |
| 13 | 発行 | `publish.py` | `issues/vol-NNN.html`・台帳追記・moushiokuri 更新・index 再生成 |
| 14 | コミット&プッシュ | actions(`if: always()` で desk/ は必ず) | main へ |
| 15 | Pages デプロイ | actions/deploy-pages | 公開 |

設計原則:

- **条件分岐は jq の小ステップ**が JSON の判定フィールド(verdict / hantei)を読んで step outputs にセットする。LLM に分岐判断をさせない
- **フレッシュアイズ**: 各工程は独立した claude-code-action 呼び出しであり、前工程の思考コンテキストを持ち込まない
- **工程クラッシュ時も休刊フロー**: `if: failure()` で GitHub Issue(vol・工程・理由)を起票し、desk/ をコミットして終了。台帳に載るまで vol は採番されないため、翌日同じ番号で再挑戦になる(欠番なし)
- 休刊(hantei=休刊)時: publish.py は発行せず、Issue を起票。desk/ はコミット

必要な Secrets:
`CLAUDE_CODE_OAUTH_TOKEN` / `RAKUTEN_APP_ID` / `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` / `TMDB_API_KEY` / `GOOGLE_PLACES_API_KEY` / `RAKUTEN_AFF_PARAM`(任意)

## スクリプト仕様

全スクリプト共通: Python 3.12、標準ライブラリのみ、fail-fast(入力 JSON の必須キーを検証し、欠けていれば非ゼロ終了+ stderr に理由)。

### seed.py

- 台帳 `editorial/daicho.md` の最終 vol +1 で採番(欠番を作らない)
- シード内容: 日付・曜日・月の異名・季節(二十四節気の近似計算)+ NHK ニュース RSS の見出し数本(外部ノイズ)
- RSS 取得失敗時は日付情報のみで続行(グレースフルフォールバック)
- 記念日の静的テーブルは持たない(LLM 生成テーブルの捏造リスクを避ける)
- **机のリセット**: `desk/vol-{NNN}/` が既に存在する場合(前日の休刊・失敗の残骸)、`desk/vol-{NNN}-retry-{YYYYMMDD}/` にリネームして保全し、今日は空の机で始める(editor-in-chief のモード判定誤爆と中間ファイル混入を防ぐ)

### verify_links.py

- researcher が Bash 経由で使う URL 死活確認。HTTP ステータスを実測し JSON で返す

### link_decorator.py(工程5)

- docs/EditorialDepartment2 版をそのまま移設。ドメイン→アフィリエイト対応表を適用し `sponsored` を確定

### kousei_machine.py(工程7前半)

- docs 版を移設し、CI では URL 死活の実測を有効化(現状の skip 固定を環境で切替可能に)

### publish.py(工程9)

- `07_kouryou.json` の hantei を読む
- 校了/責了: gera.html → `issues/vol-NNN.html` コピー、`daicho_line` を台帳へ追記、`moushiokuri` を更新(直近 14 日分保持)、index.html を台帳から再生成
- 休刊: 何もせず終了コードで知らせる(ワークフローが Issue 起票へ)

## index.html(表紙兼アーカイブ)

- 台帳 daicho.md を唯一の情報源として publish.py が決定論生成。手で編集しない
- 誌面と同じ流儀の静的 HTML: folio マストヘッド+最新号への大きな導線+全号リスト(vol / 日付 / 特集名 / ジャンル)
- `<script>` なし、`lang="ja"`、viewport・OGP あり

## テスト

- pytest で全スクリプトのユニットテスト(採番、シードのフォールバック、リンク加工、機械校正の各判定、発行の校了/責了/休刊分岐)。カバレッジ 80% 以上
- 統合テスト: docs にある vol.002 実データ(03/05/06/07 JSON・gera 相当の vol-002.html)をフィクスチャに、工程 5 → 7 前半 → 9 の決定論チェーンを通しで検証
- LLM 工程は自動テスト対象外。workflow_dispatch による手動リハーサルで確認
- `test.yml` が PR/push で pytest を実行

## スコープ外(YAGNI)

- React/Next.js/Tailwind への移行
- 天気 API・記念日データベースの統合(シードは RSS 見出しで足りる)
- コメント・RSS 配信・検索などの読者機能
- 独自ドメイン設定(Pages 公開後にいつでも追加可能)
