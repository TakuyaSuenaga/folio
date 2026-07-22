# コードレビュー報告 — folio リポジトリ全体

- 実施日: 2026-07-22
- 対象コミット: d96ccce(main)
- 対象範囲: `scripts/`(5本・約570行)、`tests/`(7本・約740行)、`.github/workflows/`(3本)、`editorial/FLOW.md` とスクリプトの整合性
- 対象外: `.claude/skills/` のプロンプト内容(コードではなく編集方針のため)、`desk/`・`issues/` の生成物
- 方法: 全ファイル精読+テストスイート実行+主要指摘の動的再現(「再現済み」と記載のある指摘は実際にコードを動かして確認した)

## 総評

**全体として高品質**。「機械にできることをLLMにさせない」という設計原則が一貫しており、決定論スクリプトは標準ライブラリのみ・小さく・読みやすい。テストは55件全て成功、カバレッジ94%(基準80%を上回る)。AAA構造・記述的なテスト名・エッジケース(rel属性順序・HTMLエスケープ・JST日付境界・入力の非破壊)への配慮は模範的である。

一方で、この設計の生命線である**決定論ゲート(kousei_machine.py)に迂回可能な穴**があり(HIGH 1件)、LLM工程への**ツール権限が全工程で一律に広い**(HIGH 1件)。いずれも修正は小さい。CRITICAL(即時のデータ損失・直接的な脆弱性)は無し。

| 深刻度 | 件数 |
|--------|------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 6 |
| INFO | 3 |

---

## HIGH

### H-1. 決定論ゲートのHTML検査が大文字タグ・シングルクォート属性で迂回できる【再現済み】

`scripts/kousei_machine.py` の検査正規表現・文字列照合はすべて小文字・ダブルクォート前提である。

- `"<script" not in html`(kousei_machine.py:96)— `<SCRIPT>` は検出されない
- `HREF_SRC_RE = re.compile(r'(?:href|src)="([^"]*)"')`(kousei_machine.py:23)— `href='javascript:alert(1)'`(単引用符)は `unsafe_schemes` にも `unknown_external` にも掛からない
- `REL_ATTR_RE`(kousei_machine.py:22)も同様に単引用符非対応
- ワークフロー側の検品 `! grep -q "<script"`(daily-issue.yml:125)も大文字を見逃す

再現結果(vol-002フィクスチャに `<SCRIPT>alert(1)</SCRIPT>` と `<a href='javascript:alert(2)'>` を注入):

```
html_ok  → True(Falseであるべき)
unsafe_schemes → [](javascript:が検出されない)
links_ok → True
```

**リスク**: ゲラを組むのは毎日再生成されるLLM(art-director)であり、上流データ(書名・説明文・RSS見出し)経由のプロンプトインジェクションで悪意あるHTMLが出力された場合、この機械ゲートが最後の決定論的防壁になる。現状は大文字・単引用符という自明な変形で素通りし、公開サイト(GitHub Pages)へのXSS・改ざんが「校正・校了のLLMが見逃せば」到達する。fail-openの穴である点がMEDIUM以下の指摘と質的に異なる。

**修正案**(kousei_machine.py):

```python
HREF_SRC_RE = re.compile(r'(?:href|src)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.IGNORECASE)
REL_ATTR_RE = re.compile(r'<a\b[^>]*\brel\s*=\s*(?:"([^"]*)"|\'([^\']*)\')[^>]*>', re.IGNORECASE)
# scriptタグ検査は
not re.search(r"<script", html, re.IGNORECASE)
```

あわせて daily-issue.yml:125 を `grep -qi` に。インラインイベントハンドラ(`onerror=` 等)の検査追加も検討に値する(現状は href/src のスキームしか見ていない)。

### H-2. 全LLM工程に無制限Bash+書き込みトークンが渡っており、外部データ経由のプロンプトインジェクション面が広い

`daily-issue.yml` の8つのclaude-code-action工程すべてが `--allowedTools Bash,Read,Write,Edit,Glob,Grep`(制限パターン無しのBash)で動く。ランナー環境には `CLAUDE_CODE_OAUTH_TOKEN`、`GOOGLE_PLACES_API_KEY`(工程2)、`contents: write` の `GITHUB_TOKEN` が存在する。

一方、LLMのコンテキストには信頼できない外部文字列が流れ込む: NHK RSS見出し(seed.md経由で工程1へ)、楽天ブックス・iTunes・Places APIの応答(書名・説明文・レビュー等。工程2で取得され03/05経由で下流全工程へ)。公開カタログの作品タイトルは第三者が自由に登録できるため、現実的な注入経路である。注入が成立した工程はBashで秘密の窃取・任意のリポジトリ改変(mainへ直接push可能)まで到達しうる。

**修正案**(最小権限化):

- Bashが本当に必要な工程は2(API取得)と7(検証)程度。工程1・3・4・6・8は `Read,Write,Edit,Glob,Grep` で足りる可能性が高い
- Bashを残す工程も `Bash(python scripts/*)` `Bash(curl *)` のようなコマンドパターン制限にする
- `GOOGLE_PLACES_API_KEY` は現状どおり工程2のみに渡す(これは正しくできている)

---

## MEDIUM

### M-1. publish.py が型検証前に書き込みを開始し、失敗時に中途半端な状態がmainにコミットされる【再現済み】

`REQUIRED_KEYS` の検証(publish.py:151)はキーの**存在**のみで**型**を見ない。`moushiokuri` が文字列以外(LLMがリストで出力する等)の場合、`update_moushiokuri` 内の `re.split`(publish.py:123)で TypeError になるが、その時点で既に:

- `issues/vol-002.html` のコピー済み(publish.py:181)
- 台帳への追記済み(publish.py:188)
- index.html は**未再生成**

再現結果: `moushiokuri: ["リスト", "形式"]` で `TypeError` 発生、`issues/vol-002.html` 存在=True、台帳追記=True、index.html=False。

さらにワークフローのコミット工程は `if: always()`(daily-issue.yml:226)なので、この不整合状態(号ページは公開ツリーに入ったがindexに載らず、台帳は消費済み、Pagesデプロイはジョブ失敗でスキップ)が**mainにpushされる**。復旧は手作業になる。

**修正案**: 検証と純粋な計算(新しい台帳テキスト・申し送りテキスト・index HTML の生成)をすべて先に済ませ、ファイル書き込みを関数末尾にまとめる。これで publish がほぼアトミックになり、型逸脱はどの段階でも書き込みゼロで落ちる。最低限なら `isinstance(kouryou["moushiokuri"], str)` と `isinstance(kouryou["daicho_line"], str)` を最初の書き込み前に検証する。

### M-2. リンク照合が `&` のHTMLエスケープに非対応 — ADが正しくエスケープした日に発行が止まる【再現済み】

原稿一致チェックはエスケープ両対応(`(t in html) or (html_mod.escape(t) in html)`、kousei_machine.py:56)なのに、リンク照合は生文字列のみ:

- `link_present = {l["url"]: (l["url"] in html) ...}`(kousei_machine.py:59)
- `ext_hrefs` の捕捉値も unescape せず `known` と比較(kousei_machine.py:64-74)

現状のゲラはURLを生の `&` で書く慣習(vol-005の fonts URL で確認)なので動いているが、ADはLLMであり、HTML的に**正しい** `&amp;` エスケープをした瞬間に `link_present` 偽陰性+`unknown_external` 偽陽性で機械チェックが落ちる。

再現結果: `?a=1&b=2` を含むURLを `&amp;` でエスケープした href で組むと `link_present=False`、`unknown_external=['https://example.com/item?a=1&amp;b=2']`。

fail-closed(誤って公開はしない)方向ではあるが、クエリ付きURL(Places写真・アフィリエイトパラメータ付与後の楽天URL)が入った号から日刊が止まる。**楽天アフィリエイトIDを付与し始めると複数パラメータURLが常態化するため、顕在化は時間の問題**。

**修正案**: 捕捉した属性値を `html_mod.unescape()` してから比較する。`link_present` 側は `url in html or html_mod.escape(url, quote=False) in html`。

### M-3. `$GITHUB_OUTPUT` へのLLM由来値の直接書き込み(出力インジェクション面)

daily-issue.yml:91 と 164 で、LLMが書いたJSONの値を `echo "verdict=$(jq -r ...)" >> "$GITHUB_OUTPUT"` している。値に改行が含まれると後続行が追加の出力定義として解釈される(例: `"休刊\nhantei=校了"` は最終的に `hantei=校了` が勝つ)。

現状は下流で publish.py が hantei を再検証するため fail-closed に倒れる(検証したところ、偽の校了を注入しても publish は07を直接読むので休刊なら exit 2 で止まる)が、分岐制御(`if:`)の判断材料が汚染可能なのは好ましくない。

**修正案**: 値を許容リストで検証してから書く。

```bash
hantei=$(jq -r '.hantei' "$file")
case "$hantei" in 校了|責了|休刊) ;; *) echo "不正なhantei"; exit 1;; esac
printf 'hantei=%s\n' "$hantei" >> "$GITHUB_OUTPUT"
```

---

## LOW

### L-1. kousei_machine.py:73 — ホスト抽出の `re.match(...).group(1)` が `http:///path` 形URLで AttributeError

`ext_hrefs` の捕捉パターン `https?://[^"]+` は `http:///path`(ホスト空)も通すが、続くホスト抽出 `re.match(r"https?://([^/]+)", u)` は None を返しクラッシュする。検査失敗として扱われず未捕捉例外で工程7全体が落ちる。match失敗時は `unknown` 扱いにするのが安全。

### L-2. publish.py:106 — `render_index` が「台帳の最終行=最新号」を仮定

`latest = entries[-1]` は追記順に依存する。台帳を手で編集して順序が崩れると最新号表示とアーカイブ順が狂う。`max(entries, key=lambda x: x["vol"])` とvol降順ソートにすれば台帳の行順に依存しない。

### L-3. publish.py:212 — `int(argv[0])` が非数値引数で生トレースバック

`python scripts/publish.py abc` で ValueError のトレースバックが出る。usage メッセージの SystemExit に落とすべき(他のエラーは全て丁寧に整形されているので、ここだけ粗い)。

### L-4. verify_links.py:32 — `except Exception: return None` が失敗理由を完全に握りつぶす

None=到達不能という設計自体は妥当だが、DNS失敗・タイムアウト・SSLエラーの区別がログにも残らず、リンク切れ調査時に再実測が必要になる。stderr に一行(`[warn] {url}: {e}`)出すだけで運用性が上がる。コーディング規約の「Never silently swallow errors」にも沿う。

### L-5. Secretsスキャンの対象が `GOOGLE_PLACES_API_KEY` 1件のハードコードリスト

daily-issue.yml:207 の `for name in GOOGLE_PLACES_API_KEY;` は秘密を追加するたびに手動更新が必要で、忘れると検査対象外になる。少なくともコメントで「秘密を追加したらここにも追加」と明記するか、ループ対象を先頭で変数宣言して目立たせる。なお `RAKUTEN_AFF_PARAM` は公開URLに載る設計値なのでスキャン対象外が正しい(その旨のコメントがあると将来の誤追加を防げる)。

### L-6. desk/ に `02_kouho_temp.json` 等の作業残骸がコミットされている

`desk/vol-003-retry-20260720-3/` に `02_kouho_temp.json`・`02_kouho_temp2.json` が残る。「desk/は全てコミットする」原則には反しないが、researcher スキル側で一時ファイルを片付けてから終了する規約を足すと台帳資産のノイズが減る。

---

## INFO(判断の明文化を推奨)

- **I-1**: daily-issue.yml の工程5(リンク加工)に `RAKUTEN_AFF_PARAM` が env で渡されていないため、本番でアフィリエイトIDが付与されることは現状ない(sponsored=True のPR表記だけが付く)。未契約期間の意図的な状態なら、ワークフローにその旨のコメントを残すと将来の「なぜ付かない?」調査を省ける。
- **I-2**: `AFF_TABLE`(link_decorator.py:18)は完全一致のため、`hb.afl.rakuten.co.jp` や `a.r10.to` などアフィリエイト形状のURLが原稿に紛れた場合 sponsored=False(PR表記なし)になる。researcher が生成しない前提だが、校閲観点ではこれらのドメインを検出して警告する価値がある(ステマ規制方向の取りこぼし防御)。
- **I-3**: ローカル実行はPython 3.11、CIは3.12。使用構文は3.10+のため挙動差は無いが、CLAUDE.mdの「Python 3.12」に合わせるならローカルも揃えると安全。

---

## 良かった点

- **設計原則の徹底**: リンク加工・照合・発行が決定論スクリプトに隔離され、LLM工程と明確に分離。FLOW.mdと実装(ワークフロー・スクリプト)の間に矛盾は見つからなかった
- **テスト品質**: 55件全pass・カバレッジ94%。AAA構造、`test_reset_desk_avoids_collision` のような衝突エッジ、`test_decorated_at_uses_jst_not_utc` のJST日付境界、`test_unknown_domain_...` での入力非破壊(イミュータビリティ)検証まで揃う
- **fail-closedの姿勢**: publish は書き込み前に vol 不一致・daicho_line 形式を検証し、休刊はvolを消費しない。既知ホスト許可制(`known` はJSONに載った事実で許可、ホスト直書き許可ではない)も堅い
- **XSS対策**: `render_index` はユーザー由来文字列を全て `html.escape`(テストで担保)
- **CI衛生**: concurrency group・timeout-minutes・ジョブ別の最小permissions・Secretsスキャン・工程ごとの検品(jq)と、日次自動運用への備えが行き届いている
- **規約準拠**: 全ファイル800行未満・関数50行未満・深いネスト無し・マジックナンバーは定数化済み

## チェックリスト(コーディング規約より)

| 項目 | 判定 |
|------|------|
| 可読性・命名 | ✅ |
| 関数<50行・ファイル<800行 | ✅ |
| ネスト≦4 | ✅ |
| エラーハンドリング | ⚠️ M-1(型検証)・L-4(silent except) |
| ハードコード秘密 | ✅ 無し |
| console.log/デバッグ残骸 | ✅ 無し |
| テスト存在・カバレッジ80%+ | ✅ 94% |
| イミュータブル操作 | ✅ |

## 推奨対応順

1. **H-1**: 正規表現の大文字・単引用符対応+`grep -qi`(小改修・効果大)
2. **M-1**: publish.py を「全検証→全計算→全書き込み」の順に再構成
3. **M-2**: リンク照合の unescape 対応(楽天アフィリエイトID導入前に必須)
4. **H-2**: ワークフローの allowedTools 最小化(工程ごとに削る)
5. M-3以下は随時
