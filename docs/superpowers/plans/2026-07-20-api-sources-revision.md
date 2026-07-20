# folio APIソース改訂 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 取得できなかった有料APIキー(楽天ブックス・Spotify・TMDB)への依存を、キー不要の代替API(NDLサーチ・openBD・iTunes Search API)に置き換える。

**Architecture:** 変更はデータソース定義のみ。パイプライン構造・スクリプト・テストは不変。researcher スキルのソース表、ワークフローの Secrets 参照、README、スペックの4ファイルを改訂する。

**Tech Stack:** 既存のまま(Python 3.12 標準ライブラリ / GitHub Actions / claude-code-action)

**Spec:** `docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md`(Task 4 で改訂記録を追記)

---

## 背景(実装者向け)

ユーザーが取得できたキー/使えるAPI:

| API | 状態 | 用途 |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 登録済み | 全LLM工程 |
| `GOOGLE_PLACES_API_KEY` | 登録済み | cafe / restaurant |
| openBD | キー不要 | 書籍メタデータ照合(ISBN起点。**検索不可**) |
| NDLサーチ(国立国会図書館) | キー不要 | 書籍のキーワード検索 → ISBN取得 |
| iTunes Search API | キー不要 | film / music の検索 |
| 楽天ブックス / Spotify / TMDB | **使わない**(有料・取得不可) | — |

方針:
- book/poetry は「NDLサーチで検索 → openBD で照合」の二段構え。openBD にヒットしない書籍は候補にしない(実在チェーンの担保)
- film/music は iTunes Search API で存続(8ジャンル全部維持)
- `scripts/link_decorator.py` の楽天アフィリエイト対応表とそのテストは**温存**(将来の再契約時にそのまま使う。楽天リンクが発生しなければ死にコードではなく待機コード)
- ブランチ `feat/api-sources-revision` で作業し、最後にPRを作る

## 変更ファイル

- Modify: `.claude/skills/researcher/SKILL.md`(ソース表の差し替え)
- Modify: `.github/workflows/daily-issue.yml`(未契約Secretsの除去)
- Modify: `README.md`(Secrets表の更新)
- Modify: `docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md`(改訂記録)

---

### Task 0: 作業ブランチ作成

- [ ] **Step 1: ブランチを切る**

```bash
git checkout -b feat/api-sources-revision
```

---

### Task 1: researcher スキルのソース表を差し替え

**Files:**
- Modify: `.claude/skills/researcher/SKILL.md`

- [ ] **Step 1: ジャンル別ソース表を置換**

現在の内容(20行目付近):

```markdown
| genre | 主API | 備考 |
|---|---|---|
| book / poetry | 楽天ブックスAPI, openBD | ISBN起点。書影URLは楽天経由のもののみ可 |
| film | TMDB系 | メタ取得用。商用利用条件に留意し、画像は候補に含めない |
| music | Spotify API | アルバム単位。プレビュー/外部URLはAPIレスポンスの値のみ |
| cafe / restaurant | Google Places API | まちかわと同一の資産。place_id必須。営業時間は収集しない(変動が速く誌面に載せない) |
| photo / architecture | 書籍として楽天/openBDから引く、または所在地をPlacesで実在確認 | 建築は竣工年・所在地の一次確認を優先 |

APIキーは環境変数から。レートリミットに配慮し、1発注あたり検索は数回まで。
```

これを以下に置換する:

```markdown
| genre | 主API | 備考 |
|---|---|---|
| book / poetry | NDLサーチ + openBD(いずれもキー不要) | `https://ndlsearch.ndl.go.jp/api/opensearch?title={query}&cnt=10` で検索してISBNを得て、`https://api.openbd.jp/v1/get?isbn={isbn}` で照合する。openBDにヒットしない書籍は候補にしない。source_api は "ndl+openbd"、source_id はISBN。書影は使わない |
| film | iTunes Search API(キー不要) | `https://itunes.apple.com/search?term={query}&country=JP&media=movie&limit=10`。source_id は trackId。リンクはレスポンスの trackViewUrl のみ。画像は候補に含めない |
| music | iTunes Search API(キー不要) | `https://itunes.apple.com/search?term={query}&country=JP&media=music&entity=album&limit=10`。アルバム単位。source_id は collectionId。リンクはレスポンスの collectionViewUrl のみ |
| cafe / restaurant | Google Places API | まちかわと同一の資産。place_id必須。営業時間は収集しない(変動が速く誌面に載せない) |
| photo / architecture | 書籍としてNDL/openBDから引く、または所在地をPlacesで実在確認 | 建築は竣工年・所在地の一次確認を優先 |

APIキーが必要なのはPlacesのみ(環境変数 `GOOGLE_PLACES_API_KEY`)。他はキー不要。レートリミットに配慮し、1発注あたり検索は数回まで。
```

- [ ] **Step 2: 検証**

```bash
grep -c "ndlsearch\|itunes.apple.com\|openbd" .claude/skills/researcher/SKILL.md   # 1以上
grep -c "楽天ブックスAPI\|Spotify\|TMDB" .claude/skills/researcher/SKILL.md || echo "0 = OK"
```

Expected: 新APIが載り、旧API名が researcher スキルから消えている(0 = OK が出る)

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/researcher/SKILL.md
git commit -m "feat: リサーチのソースをキー不要API(NDL+openBD/iTunes)に切替"
```

---

### Task 2: daily-issue.yml から未契約 Secrets を除去

**Files:**
- Modify: `.github/workflows/daily-issue.yml`(3箇所)

- [ ] **Step 1: 工程2 リサーチの env を縮小**

現在(48〜52行目付近):

```yaml
        env:
          RAKUTEN_APP_ID: ${{ secrets.RAKUTEN_APP_ID }}
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          TMDB_API_KEY: ${{ secrets.TMDB_API_KEY }}
          GOOGLE_PLACES_API_KEY: ${{ secrets.GOOGLE_PLACES_API_KEY }}
```

これを以下に置換:

```yaml
        env:
          GOOGLE_PLACES_API_KEY: ${{ secrets.GOOGLE_PLACES_API_KEY }}
```

- [ ] **Step 2: 工程5 リンク加工の env を削除**

現在(103〜105行目付近):

```yaml
      - name: 工程5 リンク加工(スクリプト)
        env:
          RAKUTEN_AFF_PARAM: ${{ secrets.RAKUTEN_AFF_PARAM }}
        run: >
```

これを以下に置換(env ブロックごと削除。`RAKUTEN_AFF_PARAM` 未設定時は link_decorator がURL無改変で動く設計):

```yaml
      - name: 工程5 リンク加工(スクリプト)
        run: >
```

- [ ] **Step 3: Secretsスキャンの対象を縮小**

現在(195行目付近):

```yaml
        env:
          RAKUTEN_APP_ID: ${{ secrets.RAKUTEN_APP_ID }}
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          TMDB_API_KEY: ${{ secrets.TMDB_API_KEY }}
          GOOGLE_PLACES_API_KEY: ${{ secrets.GOOGLE_PLACES_API_KEY }}
```

を:

```yaml
        env:
          GOOGLE_PLACES_API_KEY: ${{ secrets.GOOGLE_PLACES_API_KEY }}
```

に、同ステップ内のループ:

```bash
          for name in RAKUTEN_APP_ID SPOTIFY_CLIENT_ID SPOTIFY_CLIENT_SECRET TMDB_API_KEY GOOGLE_PLACES_API_KEY; do
```

を:

```bash
          for name in GOOGLE_PLACES_API_KEY; do
```

に置換する。

- [ ] **Step 4: 検証**

```bash
grep -c "RAKUTEN\|SPOTIFY\|TMDB" .github/workflows/daily-issue.yml || echo "0 = OK"
python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-issue.yml')); print('YAML OK')"
```

Expected: `0 = OK` と `YAML OK`(pyyaml が無ければ `pip install pyyaml` してから)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily-issue.yml
git commit -m "ci: 未契約API(楽天/Spotify/TMDB)のSecrets参照を除去"
```

---

### Task 3: README の Secrets 表を更新

**Files:**
- Modify: `README.md`(17〜21行目付近の表)

- [ ] **Step 1: Secrets 表を置換**

現在:

```markdown
| `RAKUTEN_APP_ID` | 楽天ブックスAPI(book/poetry/photo/architecture) | ✔ |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Spotify API(music) | ✔ |
| `TMDB_API_KEY` | TMDB(film) | ✔ |
| `GOOGLE_PLACES_API_KEY` | Google Places(cafe/restaurant) | ✔ |
| `RAKUTEN_AFF_PARAM` | 楽天アフィリエイトID。`key=value` 形式 | 任意 |
```

これを以下に置換(表ヘッダと `CLAUDE_CODE_OAUTH_TOKEN` 行は既存のまま残す):

```markdown
| `GOOGLE_PLACES_API_KEY` | Google Places(cafe/restaurant) | ✔ |
```

さらに表の直後に以下の段落を追加:

```markdown
書籍(book/poetry/photo/architecture)は NDLサーチ + openBD、film/music は iTunes Search API を使う——いずれもAPIキー不要。
楽天アフィリエイト(`RAKUTEN_AFF_PARAM`)は楽天API契約後に再開する。`scripts/link_decorator.py` の対応表は温存してある。
```

- [ ] **Step 2: 検証**

```bash
grep -c "SPOTIFY\|TMDB\|RAKUTEN_APP_ID" README.md || echo "0 = OK"
grep -c "iTunes Search API" README.md   # 1以上
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: Secrets表をキー不要API構成に更新"
```

---

### Task 4: スペックに改訂記録を追記

**Files:**
- Modify: `docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md`

- [ ] **Step 1: 決定事項の表の「外部API」行を更新**

現在:

```markdown
| 外部 API | 楽天ブックス / openBD / Spotify / TMDB / Google Places — 全キー取得済み前提 |
```

を:

```markdown
| 外部 API | NDLサーチ + openBD(book系)/ iTunes Search API(film・music)/ Google Places(cafe・restaurant)。キー必須は Places のみ(2026-07-20 改訂) |
```

に置換する。

- [ ] **Step 2: 文末に改訂履歴セクションを追加**

```markdown
## 改訂履歴

### 2026-07-20: APIソース改訂

楽天ブックス・Spotify・TMDB のキーが取得不可(有料/登録不可)だったため、キー不要APIへ切替:

- book/poetry: NDLサーチ(キーワード検索→ISBN)+ openBD(ISBN照合)。openBD にヒットしない書籍は候補にしない
- film/music: iTunes Search API(source_id は trackId / collectionId)
- ジャンル8種は全て維持。必要な Secrets は `CLAUDE_CODE_OAUTH_TOKEN` と `GOOGLE_PLACES_API_KEY` の2つに縮小
- `scripts/link_decorator.py` の楽天アフィリエイト対応表は将来の再契約に備え温存
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md
git commit -m "docs: スペックにAPIソース改訂を記録"
```

---

### Task 5: 回帰確認

- [ ] **Step 1: 全テスト実行**(スクリプトは無変更なので全て通るはず)

Run: `python -m pytest tests/ -v --cov=scripts --cov-fail-under=80`
Expected: 全テスト passed、カバレッジゲート通過。失敗した場合はこの改訂とは無関係の回帰なので、原因を特定して報告する(勝手にテストを弄らない)

- [ ] **Step 2: 変更サマリの確認**

```bash
git log --oneline main..HEAD
git diff main..HEAD --stat
```

Expected: コミット4件、変更ファイル4つ(researcher SKILL / daily-issue.yml / README / spec)

---

## 実装後の手動作業(ユーザーが行う)

1. 登録済みでない Secrets(`RAKUTEN_APP_ID` 等)がリポジトリに残っていれば削除して構わない(参照は本改訂で消える)
2. PRマージ後、Actions タブから `daily-issue` を手動実行してリサーチ工程が新APIで動くか確認する
