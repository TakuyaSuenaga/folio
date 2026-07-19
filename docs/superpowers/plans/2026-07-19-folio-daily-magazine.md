# folio 日刊Web雑誌 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI編集部が毎日 JST 0:00 に GitHub Actions で1号を制作・発行し、GitHub Pages で公開する日刊Web雑誌リポジトリを構築する。

**Architecture:** 9工程パイプライン(企画→リサーチ→執筆→校閲→リンク加工→組版→校正→校了→発行)。LLM工程は claude-code-action(Haiku)の独立呼び出し、機械工程は Python 標準ライブラリのみの決定論スクリプト。号は自己完結の生HTML。ビルドステップなし。

**Tech Stack:** Python 3.12(標準ライブラリのみ)/ pytest / GitHub Actions / anthropics/claude-code-action@v1 / GitHub Pages(actions/deploy-pages)

**Spec:** `docs/superpowers/specs/2026-07-19-folio-daily-magazine-design.md`

---

## 前提知識(実装者向け)

- この雑誌の「憲法」は `docs/EditorialDepartment2/FLOW.md`(Task 1 で `editorial/FLOW.md` に移設)。工程・スキーマ・表記規定が全て書いてある
- 判定フィールドの値: 校閲 `04_koetsu.json` の `verdict` は `pass | fix_required`。校了 `07_kouryou.json` の `hantei` は `校了 | 責了 | 休刊`
- vol.002 の実データ(`docs/EditorialDepartment2/` の JSON 群と `vol-002.html`)は検証済み: `kousei_machine.py` に通すと全項目 true になる。テストフィクスチャとして使う
- テスト実行はリポジトリルートで `python -m pytest tests/ -v`。`tests/conftest.py` が `scripts/` を import path に足す
- コミットメッセージに Claude の署名は付けない(ユーザー設定でグローバルに無効化済み)

## ファイル構成(最終形)

```
CLAUDE.md                          # Task 2
README.md                          # Task 2(Task 11 でセットアップ手順を追記)
.gitignore                         # Task 2
editorial/{FLOW.md,daicho.md,moushiokuri.md}   # Task 1
.claude/skills/{editor-in-chief,researcher,genre-editor,koetsu,kousei,art-director}/SKILL.md  # Task 1
issues/{vol-001.html,vol-002.html} # Task 1 / index.html は Task 8
tests/fixtures/vol-002/{03_genko.json,05_goudata.json,07_kouryou.json,vol-002.html}  # Task 1
tests/{conftest.py,test_link_decorator.py,test_verify_links.py,test_kousei_machine.py,test_seed.py,test_publish.py,test_integration_vol002.py}
scripts/{link_decorator.py,verify_links.py,kousei_machine.py,seed.py,publish.py}
.github/workflows/{test.yml,deploy-pages.yml,daily-issue.yml}  # Task 9, 10
```

---

### Task 1: 編集部資産の移設(editorial / skills / issues / fixtures)

**Files:**
- Create: `editorial/FLOW.md`, `editorial/daicho.md`, `editorial/moushiokuri.md`
- Create: `.claude/skills/{editor-in-chief,researcher,genre-editor,koetsu,kousei}/SKILL.md`
- Overwrite: `.claude/skills/art-director/SKILL.md`(現在 0 バイトの空ファイル。docs の 264 行版で上書きする)
- Create: `issues/vol-001.html`, `issues/vol-002.html`
- Create: `tests/fixtures/vol-002/`(4 ファイル)

- [ ] **Step 1: editorial/ を作成して永続ファイルを移設**

```bash
mkdir -p editorial desk
cp docs/EditorialDepartment2/FLOW.md editorial/FLOW.md
cp docs/EditorialDepartment2/daicho.md editorial/daicho.md
cp docs/EditorialDepartment2/moushiokuri.md editorial/moushiokuri.md
touch desk/.gitkeep   # ワークフローの git add -A desk が初回から成立するように
```

- [ ] **Step 2: スキル6役職をコピー**(researcher と art-director は EditorialDepartment2 版が最新)

```bash
mkdir -p .claude/skills/editor-in-chief .claude/skills/researcher .claude/skills/genre-editor .claude/skills/koetsu .claude/skills/kousei .claude/skills/art-director
cp docs/EditorialDepartment1/SKILL.md .claude/skills/editor-in-chief/SKILL.md
cp docs/EditorialDepartment2/SKILL.md .claude/skills/researcher/SKILL.md
cp docs/EditorialDepartment1/mnt/user-data/outputs/skills/genre-editor/SKILL.md .claude/skills/genre-editor/SKILL.md
cp docs/EditorialDepartment1/mnt/user-data/outputs/skills/koetsu/SKILL.md .claude/skills/koetsu/SKILL.md
cp docs/EditorialDepartment1/mnt/user-data/outputs/skills/kousei/SKILL.md .claude/skills/kousei/SKILL.md
cp docs/EditorialDepartment2/mnt/user-data/outputs/skills/art-director/SKILL.md .claude/skills/art-director/SKILL.md
```

- [ ] **Step 3: 既刊2号を issues/ へ、vol.002 実データをフィクスチャへ**

```bash
mkdir -p issues tests/fixtures/vol-002
cp docs/EditorialDepartment1/vol-001.html issues/vol-001.html
cp docs/EditorialDepartment2/vol-002.html issues/vol-002.html
cp docs/EditorialDepartment2/03_genko.json tests/fixtures/vol-002/
cp docs/EditorialDepartment2/05_goudata.json tests/fixtures/vol-002/
cp docs/EditorialDepartment2/07_kouryou.json tests/fixtures/vol-002/
cp docs/EditorialDepartment2/vol-002.html tests/fixtures/vol-002/
```

- [ ] **Step 4: 検証**

```bash
for s in editor-in-chief researcher genre-editor koetsu kousei art-director; do
  grep -m1 "^name:" ".claude/skills/$s/SKILL.md"
done
wc -l .claude/skills/art-director/SKILL.md   # 264 であること(0なら上書き失敗)
ls editorial issues tests/fixtures/vol-002
```

Expected: 各スキルの `name:` が役職名と一致。art-director が 264 行。

- [ ] **Step 5: Commit**

```bash
git add editorial desk .claude/skills issues tests/fixtures
git commit -m "feat: 編集部資産を移設(FLOW・台帳・スキル6役職・既刊2号・テストフィクスチャ)"
```

---

### Task 2: CLAUDE.md / README.md / .gitignore

**Files:**
- Create: `CLAUDE.md`, `README.md`(既存1行を置換), `.gitignore`

- [ ] **Step 1: CLAUDE.md を作成**(FLOW.md の要点転記。FLOW.md 3 行目の要請)

````markdown
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
````

- [ ] **Step 2: README.md を置換**

````markdown
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
````

- [ ] **Step 3: .gitignore を作成**

```
__pycache__/
.pytest_cache/
.coverage
.DS_Store
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md .gitignore
git commit -m "docs: CLAUDE.md(FLOW要点転記)とREADMEを追加"
```

---

### Task 3: pytest 基盤 + link_decorator.py 移設

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_link_decorator.py`
- Create: `scripts/link_decorator.py`(docs からコピー、改変なし)

- [ ] **Step 1: conftest.py を作成**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
```

- [ ] **Step 2: 失敗するテストを書く** — `tests/test_link_decorator.py`

```python
import json

import link_decorator


def test_unknown_domain_is_not_sponsored_and_url_unchanged():
    # Arrange
    link = {"label": "版元ページ", "url": "https://example.com/x?a=1", "kind": "info"}

    # Act
    out = link_decorator.decorate(link)

    # Assert
    assert out["sponsored"] is False
    assert out["url"] == "https://example.com/x?a=1"
    assert "kind" not in out
    assert link["url"] == "https://example.com/x?a=1"  # 元オブジェクトを破壊しない


def test_rakuten_domain_is_sponsored_with_aff_param(monkeypatch):
    monkeypatch.setenv("RAKUTEN_AFF_PARAM", "scid=af_test123")
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/"}
    out = link_decorator.decorate(link)
    assert out["sponsored"] is True
    assert "scid=af_test123" in out["url"]


def test_rakuten_domain_without_aff_param_keeps_url(monkeypatch):
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/"}
    out = link_decorator.decorate(link)
    assert out["sponsored"] is True
    assert out["url"] == "https://books.rakuten.co.jp/rb/123/"


def test_main_writes_goudata(tmp_path, monkeypatch):
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    genko = {
        "issue": {"vol": 99, "date": "2026-07-19", "title": "テスト", "lead": "リード"},
        "items": [{"genre": "book", "cand_id": "b-01", "title": "t", "essay": "e",
                   "links": [{"label": "L", "url": "https://example.com/"}]}],
        "colophon": {"note": "VOL.099"},
    }
    src = tmp_path / "03_genko.json"
    dst = tmp_path / "05_goudata.json"
    src.write_text(json.dumps(genko, ensure_ascii=False), encoding="utf-8")

    link_decorator.main(str(src), str(dst))

    out = json.loads(dst.read_text(encoding="utf-8"))
    assert out["items"][0]["links"][0]["sponsored"] is False
    assert out["colophon"] == {"note": "VOL.099"}
    assert "decorated_at" in out
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `python -m pytest tests/test_link_decorator.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'link_decorator'`)

- [ ] **Step 4: スクリプトを移設**(改変なしのコピー)

```bash
mkdir -p scripts
cp docs/EditorialDepartment2/link_decorator.py scripts/link_decorator.py
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m pytest tests/test_link_decorator.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_link_decorator.py scripts/link_decorator.py
git commit -m "feat: 工程5リンク加工スクリプトを移設しテストを追加"
```

---

### Task 4: verify_links.py(URL死活確認)

**Files:**
- Create: `tests/test_verify_links.py`
- Create: `scripts/verify_links.py`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_verify_links.py`

```python
import io
import json
import urllib.error

import pytest

import verify_links


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_check_url_returns_status(monkeypatch):
    monkeypatch.setattr(verify_links.urllib.request, "urlopen",
                        lambda req, timeout: FakeResponse(200))
    assert verify_links.check_url("https://example.com/") == 200


def test_check_url_returns_http_error_code(monkeypatch):
    def raise_404(req, timeout):
        raise urllib.error.HTTPError("https://example.com/", 404, "NF", {}, io.BytesIO())
    monkeypatch.setattr(verify_links.urllib.request, "urlopen", raise_404)
    assert verify_links.check_url("https://example.com/") == 404


def test_check_url_returns_none_when_unreachable(monkeypatch):
    def raise_err(req, timeout):
        raise urllib.error.URLError("dns failure")
    monkeypatch.setattr(verify_links.urllib.request, "urlopen", raise_err)
    assert verify_links.check_url("https://nx.invalid/") is None


def test_main_outputs_json(monkeypatch, capsys):
    monkeypatch.setattr(verify_links, "check_url",
                        lambda u: 200 if "ok" in u else None)
    verify_links.main(["https://ok.example/", "https://ng.example/"])
    out = json.loads(capsys.readouterr().out)
    assert out["https://ok.example/"]["ok"] is True
    assert out["https://ng.example/"]["ok"] is False
    assert out["https://ng.example/"]["url_status"] is None
    assert "checked_at" in out["https://ok.example/"]


def test_main_without_urls_exits():
    with pytest.raises(SystemExit):
        verify_links.main([])
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_verify_links.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 実装** — `scripts/verify_links.py`

```python
#!/usr/bin/env python3
"""folio: URL死活確認(決定論)

usage: python scripts/verify_links.py URL [URL...]
結果を {url: {url_status, ok, checked_at}} のJSONでstdoutに出す。
researcherが02_kouho.jsonのverify欄を埋めるために使う。
kousei_machine.pyもCIでのリンク死活実測に使う。
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

TIMEOUT_SEC = 10
USER_AGENT = "Mozilla/5.0 (compatible; folio-linkcheck/1.0)"
HTTP_ERROR_THRESHOLD = 400


def check_url(url: str) -> int | None:
    """HTTPステータスを実測する。到達不能ならNone。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def main(urls: list[str]) -> None:
    if not urls:
        raise SystemExit("usage: verify_links.py URL [URL...]")
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {}
    for u in urls:
        status = check_url(u)
        result[u] = {
            "url_status": status,
            "ok": status is not None and status < HTTP_ERROR_THRESHOLD,
            "checked_at": checked_at,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_verify_links.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_verify_links.py scripts/verify_links.py
git commit -m "feat: URL死活確認スクリプトを追加"
```

---

### Task 5: kousei_machine.py 移設+URL実測の切替

**Files:**
- Create: `tests/test_kousei_machine.py`
- Create: `scripts/kousei_machine.py`(docs 版を改修: `build_machine()` 抽出+`FOLIO_CHECK_URLS=1` でリンク死活実測)

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_kousei_machine.py`

```python
import json
from pathlib import Path

import kousei_machine

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vol-002"


def load_fixture():
    d = json.loads((FIXTURES / "05_goudata.json").read_text(encoding="utf-8"))
    html = (FIXTURES / "vol-002.html").read_text(encoding="utf-8")
    return d, html


def test_vol002_passes_all_checks():
    d, html = load_fixture()
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    assert machine["genko_match"] is True
    assert machine["links_ok"] is True
    assert machine["pr_labels_ok"] is True
    assert machine["html_ok"] is True
    assert machine["okuzuke_ok"] is True
    assert machine["url_status"].startswith("skip")


def test_tampered_essay_fails_genko_match():
    d, html = load_fixture()
    d["items"][0]["essay"] = d["items"][0]["essay"] + "改変"
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    assert machine["genko_match"] is False


def test_unknown_external_link_fails_links_ok():
    d, html = load_fixture()
    html = html.replace("</body>", '<a href="https://evil.example/x">x</a></body>')
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    assert machine["links_ok"] is False
    assert "https://evil.example/x" in machine["links_detail"]["unknown_external"]


def test_check_urls_records_measured_status(monkeypatch):
    d, html = load_fixture()
    monkeypatch.setattr(kousei_machine.verify_links, "check_url", lambda u: 200)
    machine = kousei_machine.build_machine(d, html, check_urls=True)
    assert isinstance(machine["url_status"], list)
    assert all(e["status"] == 200 for e in machine["url_status"])


def test_main_writes_output(tmp_path, monkeypatch):
    monkeypatch.delenv("FOLIO_CHECK_URLS", raising=False)
    out = tmp_path / "machine.json"
    kousei_machine.main(str(FIXTURES / "05_goudata.json"),
                        str(FIXTURES / "vol-002.html"), str(out))
    machine = json.loads(out.read_text(encoding="utf-8"))
    assert machine["genko_match"] is True
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_kousei_machine.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 実装** — `scripts/kousei_machine.py`(docs 版のロジックを維持し、関数抽出+URL実測を追加)

```python
#!/usr/bin/env python3
"""folio 工程7(前半): 校正の機械チェック(決定論)

05_goudata.json とゲラHTMLを照合し、machine結果JSONを出力する。
- 原稿一致(lead/essayの完全一致包含)
- リンク照合(全URL存在、sponsoredのrel/[PR]、05に無い外部hrefの検出)
- HTML健全性(lang/h1/script不在/viewport/OGP/外部リソース許可制)
- 規定文言(奥付のアフィリエイト包括表記)
- リンク死活: 環境変数 FOLIO_CHECK_URLS=1 のときのみ実測(CI用)
"""
import json
import os
import re
import sys

import verify_links

OKUZUKE = "本誌の一部リンクはアフィリエイトプログラムを利用しており、リンク経由の購入等により発行元が収益を得ることがあります。"
ALLOWED_RESOURCE_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com", "tshop.r10s.jp"}


def build_machine(d: dict, html: str, check_urls: bool) -> dict:
    texts = [("lead", d["issue"]["lead"])] + [
        (f"items[{i}].essay", it["essay"]) for i, it in enumerate(d["items"])
    ]
    genko = {name: (t in html) for name, t in texts}

    links = [l for it in d["items"] for l in it["links"]]
    link_present = {l["url"]: (l["url"] in html) for l in links}
    n_sp = sum(1 for l in links if l["sponsored"])
    rel_ok = html.count('rel="sponsored noopener"') == n_sp
    pr_ok = html.count("[PR]") == n_sp

    ext_hrefs = set(re.findall(r'(?:href|src)="(https?://[^"]+)"', html))
    known = {l["url"] for l in links}
    unknown = []
    for u in ext_hrefs:
        host = re.match(r"https?://([^/]+)", u).group(1)
        if u not in known and host not in ALLOWED_RESOURCE_HOSTS:
            unknown.append(u)

    if check_urls:
        url_status = [{"url": l["url"], "status": verify_links.check_url(l["url"])}
                      for l in links]
    else:
        url_status = "skip(FOLIO_CHECK_URLS未設定)"

    return {
        "genko_match": all(genko.values()),
        "genko_detail": genko,
        "links_ok": all(link_present.values()) and not unknown,
        "links_detail": {"present": link_present, "unknown_external": sorted(unknown)},
        "pr_labels_ok": rel_ok and pr_ok,
        "html_ok": all([
            'lang="ja"' in html,
            html.count("<h1") == 1,
            "<script" not in html,
            'name="viewport"' in html,
            'property="og:title"' in html,
        ]),
        "okuzuke_ok": OKUZUKE in html,
        "url_status": url_status,
    }


def main(goudata_path: str, gera_path: str, out_path: str) -> None:
    with open(goudata_path, encoding="utf-8") as f:
        d = json.load(f)
    with open(gera_path, encoding="utf-8") as f:
        html = f.read()
    machine = build_machine(d, html, os.environ.get("FOLIO_CHECK_URLS") == "1")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(machine, f, ensure_ascii=False, indent=2)
    print(json.dumps(machine, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_kousei_machine.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_kousei_machine.py scripts/kousei_machine.py
git commit -m "feat: 機械校正スクリプトを移設しURL実測をCI用に切替可能にする"
```

---

### Task 6: seed.py(号数決定・机リセット・起点シード)

**Files:**
- Create: `tests/test_seed.py`
- Create: `scripts/seed.py`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_seed.py`

```python
from datetime import date

import pytest

import seed

DAICHO = """# folio 特集台帳

vol.001 | 2026-07-19 | 空港の時間 | music,film,architecture | 試し刷
vol.002 | 2026-07-19 | 氷 | book,cafe | 迫る氷と消える氷
"""


def test_next_vol_increments_last():
    assert seed.next_vol(DAICHO) == 3


def test_next_vol_defaults_to_1():
    assert seed.next_vol("# 台帳\n") == 1


@pytest.mark.parametrize("d,name", [
    (date(2026, 7, 19), "小暑"),
    (date(2026, 7, 22), "大暑"),
    (date(2026, 1, 2), "冬至"),
    (date(2026, 3, 20), "春分"),
])
def test_current_sekki(d, name):
    assert seed.current_sekki(d) == name


def test_reset_desk_renames_existing(tmp_path):
    desk = tmp_path / "vol-003"
    desk.mkdir()
    (desk / "01_kikaku.json").write_text("{}", encoding="utf-8")

    seed.reset_desk(desk, "20260720")

    assert not desk.exists()
    assert (tmp_path / "vol-003-retry-20260720" / "01_kikaku.json").exists()


def test_reset_desk_avoids_collision(tmp_path):
    (tmp_path / "vol-003-retry-20260720").mkdir()
    desk = tmp_path / "vol-003"
    desk.mkdir()

    seed.reset_desk(desk, "20260720")

    assert (tmp_path / "vol-003-retry-20260720-2").exists()


def test_reset_desk_noop_when_missing(tmp_path):
    seed.reset_desk(tmp_path / "vol-003", "20260720")  # 例外にならないこと


def test_build_seed_with_headlines():
    text = seed.build_seed(3, date(2026, 7, 20), ["見出しA", "見出しB"])
    assert "vol.003" in text
    assert "- 見出しA" in text
    assert "文月" in text
    assert "(月)" in text


def test_build_seed_without_headlines():
    text = seed.build_seed(3, date(2026, 7, 20), [])
    assert "取得できず" in text


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>NHK NEWS</title>
<item><title>headline one</title></item>
<item><title>headline two</title></item>
</channel></rss>"""


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit=-1):
        return RSS


def test_fetch_headlines_parses_rss(monkeypatch):
    monkeypatch.setattr(seed.urllib.request, "urlopen",
                        lambda req, timeout: FakeResponse())
    assert seed.fetch_headlines() == ["headline one", "headline two"]


def test_fetch_headlines_returns_empty_on_error(monkeypatch):
    def boom(req, timeout):
        raise OSError("network down")
    monkeypatch.setattr(seed.urllib.request, "urlopen", boom)
    assert seed.fetch_headlines() == []


def test_main_creates_desk_and_prints_outputs(tmp_path, monkeypatch, capsys):
    (tmp_path / "editorial").mkdir()
    (tmp_path / "editorial" / "daicho.md").write_text(DAICHO, encoding="utf-8")
    monkeypatch.setattr(seed, "fetch_headlines", lambda: [])

    seed.main(tmp_path)

    out = capsys.readouterr().out
    assert "vol=3" in out
    assert "nnn=003" in out
    assert (tmp_path / "desk" / "vol-003" / "seed.md").exists()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_seed.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 実装** — `scripts/seed.py`

```python
#!/usr/bin/env python3
"""folio 工程0: 号数決定と起点シード生成(決定論+外部ノイズ)

- editorial/daicho.md の最終volから次号を採番する(台帳に載るまで番号は消費されない=休刊は欠番を作らない)
- desk/vol-{NNN}/ が残っていれば(前日の休刊・失敗の残骸)retryとして退避し、空の机で始める
- シード(日付・曜日・月の異名・節気・NHKニュースRSS見出し)を desk/vol-{NNN}/seed.md に書く
- stdout に GITHUB_OUTPUT 形式(vol=N / nnn=NNN)を出力する
"""
import html
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
NHK_RSS_URL = "https://www.nhk.or.jp/rss/news/cat0.xml"
RSS_TIMEOUT_SEC = 10
RSS_MAX_BYTES = 512 * 1024  # 肥大したレスポンスは読まない(DoS耐性)
MAX_HEADLINES = 5
# XMLパーサは使わない: stdlibのxml.etreeはXXE/billion-laughs耐性が無く、
# defusedxmlは「標準ライブラリのみ」の制約に反する。titleの抽出だけなので正規表現で足りる
TITLE_RE = re.compile(r"<title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</title>", re.DOTALL)

YOUBI = ["月", "火", "水", "木", "金", "土", "日"]
TSUKI_INAMEI = {
    1: "睦月", 2: "如月", 3: "弥生", 4: "卯月", 5: "皐月", 6: "水無月",
    7: "文月", 8: "葉月", 9: "長月", 10: "神無月", 11: "霜月", 12: "師走",
}
# 二十四節気の近似日(年により±1日ずれるが、発想のシード用途では十分)
SEKKI = [
    ((1, 5), "小寒"), ((1, 20), "大寒"), ((2, 4), "立春"), ((2, 19), "雨水"),
    ((3, 5), "啓蟄"), ((3, 20), "春分"), ((4, 4), "清明"), ((4, 20), "穀雨"),
    ((5, 5), "立夏"), ((5, 21), "小満"), ((6, 5), "芒種"), ((6, 21), "夏至"),
    ((7, 7), "小暑"), ((7, 22), "大暑"), ((8, 7), "立秋"), ((8, 23), "処暑"),
    ((9, 7), "白露"), ((9, 23), "秋分"), ((10, 8), "寒露"), ((10, 23), "霜降"),
    ((11, 7), "立冬"), ((11, 22), "小雪"), ((12, 7), "大雪"), ((12, 21), "冬至"),
]
VOL_RE = re.compile(r"^vol\.(\d+)", re.MULTILINE)


def next_vol(daicho_text: str) -> int:
    vols = [int(m) for m in VOL_RE.findall(daicho_text)]
    return max(vols) + 1 if vols else 1


def current_sekki(d: date) -> str:
    name = "冬至"  # 1/1〜1/4 は前年の冬至の圏内
    for (m, day), n in SEKKI:
        if (d.month, d.day) >= (m, day):
            name = n
    return name


def reset_desk(desk_dir: Path, today_str: str) -> None:
    if not desk_dir.exists():
        return
    base = Path(f"{desk_dir}-retry-{today_str}")
    dest = base
    n = 2
    while dest.exists():
        dest = Path(f"{base}-{n}")
        n += 1
    desk_dir.rename(dest)
    print(f"[info] 前回の机を退避: {dest.name}", file=sys.stderr)


def fetch_headlines(url: str = NHK_RSS_URL) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "folio-seed/1.0"})
        with urllib.request.urlopen(req, timeout=RSS_TIMEOUT_SEC) as res:
            body = res.read(RSS_MAX_BYTES).decode("utf-8", errors="replace")
        titles = [html.unescape(t).strip() for t in TITLE_RE.findall(body)]
        titles = [t for t in titles if t]
        return titles[1:MAX_HEADLINES + 1]  # 先頭はチャンネル名なので捨てる
    except Exception as e:
        print(f"[warn] RSS取得失敗({e})。暦のみでシードを作る", file=sys.stderr)
        return []


def build_seed(vol: int, today: date, headlines: list[str]) -> str:
    lines = [
        f"# 起点シード vol.{vol:03d}",
        "",
        f"- 日付: {today.isoformat()}({YOUBI[today.weekday()]})",
        f"- 月の異名: {TSUKI_INAMEI[today.month]}",
        f"- 節気: {current_sekki(today)}",
        "",
        "## 今日の見出し(NHKニュースRSS)",
    ]
    if headlines:
        lines += [f"- {h}" for h in headlines]
    else:
        lines.append("- (取得できず——今日は暦だけで発想する)")
    return "\n".join(lines) + "\n"


def main(root: Path) -> None:
    daicho = root / "editorial" / "daicho.md"
    if not daicho.exists():
        raise SystemExit(f"[error] 台帳が無い: {daicho}")
    today = datetime.now(JST).date()
    vol = next_vol(daicho.read_text(encoding="utf-8"))
    nnn = f"{vol:03d}"
    desk = root / "desk" / f"vol-{nnn}"
    reset_desk(desk, today.strftime("%Y%m%d"))
    desk.mkdir(parents=True)
    (desk / "seed.md").write_text(build_seed(vol, today, fetch_headlines()),
                                  encoding="utf-8")
    print(f"vol={vol}")
    print(f"nnn={nnn}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parent.parent)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_seed.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_seed.py scripts/seed.py
git commit -m "feat: 号数決定と起点シード生成スクリプトを追加"
```

---

### Task 7: publish.py(発行・台帳追記・申し送り・index生成)

**Files:**
- Create: `tests/test_publish.py`
- Create: `scripts/publish.py`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_publish.py`

```python
import json
from pathlib import Path

import pytest

import publish

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vol-002"

DAICHO = """# folio 特集台帳

vol.001 | 2026-07-19 | 空港の時間 | music,film,architecture | 試し刷
"""


def make_repo(tmp_path, hantei="校了"):
    (tmp_path / "editorial").mkdir()
    (tmp_path / "editorial" / "daicho.md").write_text(DAICHO, encoding="utf-8")
    (tmp_path / "editorial" / "moushiokuri.md").write_text("# 申し送り\n", encoding="utf-8")
    desk = tmp_path / "desk" / "vol-002"
    desk.mkdir(parents=True)
    kouryou = json.loads((FIXTURES / "07_kouryou.json").read_text(encoding="utf-8"))
    kouryou["hantei"] = hantei
    (desk / "07_kouryou.json").write_text(
        json.dumps(kouryou, ensure_ascii=False), encoding="utf-8")
    (desk / "gera.html").write_text(
        (FIXTURES / "vol-002.html").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_parse_daicho():
    entries = publish.parse_daicho(DAICHO)
    assert entries == [{"vol": 1, "date": "2026-07-19", "title": "空港の時間",
                        "genres": "music,film,architecture", "summary": "試し刷"}]


def test_publish_kouryou_creates_issue_and_updates_records(tmp_path):
    root = make_repo(tmp_path)

    assert publish.publish(root, 2) == 0

    assert (root / "issues" / "vol-002.html").exists()
    daicho = (root / "editorial" / "daicho.md").read_text(encoding="utf-8")
    assert "vol.002 | 2026-07-19 | 氷" in daicho
    index = (root / "issues" / "index.html").read_text(encoding="utf-8")
    assert "氷" in index
    assert 'href="./vol-002.html"' in index
    moushiokuri = (root / "editorial" / "moushiokuri.md").read_text(encoding="utf-8")
    assert "## 2026-07-19 (vol.002 校了時)" in moushiokuri


def test_publish_kyukan_returns_2_and_writes_nothing(tmp_path):
    root = make_repo(tmp_path, hantei="休刊")

    assert publish.publish(root, 2) == publish.EXIT_KYUKAN

    assert not (root / "issues" / "vol-002.html").exists()
    assert "vol.002" not in (root / "editorial" / "daicho.md").read_text(encoding="utf-8")


def test_publish_missing_keys_exits(tmp_path):
    root = make_repo(tmp_path)
    (root / "desk" / "vol-002" / "07_kouryou.json").write_text(
        json.dumps({"vol": 2, "hantei": "校了"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        publish.publish(root, 2)


def test_publish_unknown_hantei_exits(tmp_path):
    root = make_repo(tmp_path, hantei="なんとなく")
    with pytest.raises(SystemExit):
        publish.publish(root, 2)


def test_update_moushiokuri_appends_and_trims():
    text = "# 申し送り\n"
    for i in range(20):
        text = publish.update_moushiokuri(
            text, f"2026-07-{i + 1:02d}", i + 1, f"メモ{i + 1:02d}")
    assert text.count("## ") == publish.MOUSHIOKURI_KEEP
    assert "メモ20" in text
    assert "メモ07" in text   # 20 - 14 + 1 = 7 番目から残る
    assert "メモ06" not in text


def test_update_moushiokuri_splits_nakaguro_bullets():
    out = publish.update_moushiokuri("# 申し送り\n", "2026-07-19", 2, "・一つ目 ・二つ目")
    assert "- 一つ目" in out
    assert "- 二つ目" in out


def test_render_index_escapes_html():
    entries = [{"vol": 1, "date": "2026-07-19", "title": "<氷>",
                "genres": "book", "summary": "a&b"}]
    html = publish.render_index(entries)
    assert "&lt;氷&gt;" in html
    assert "a&amp;b" in html
    assert "<script" not in html
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_publish.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 実装** — `scripts/publish.py`

```python
#!/usr/bin/env python3
"""folio 工程9: 発行(決定論・LLM禁止工程)

07_kouryou.json の判定を読み、校了/責了なら発行する:
- desk/vol-{NNN}/gera.html → issues/vol-{NNN}.html
- daicho_line を editorial/daicho.md へ追記
- moushiokuri を editorial/moushiokuri.md へ追記(直近14エントリ保持)
- editorial/daicho.md から issues/index.html を再生成
休刊なら何もせず exit 2(ワークフローがIssueを起票する)。

usage:
  python scripts/publish.py <vol番号>
  python scripts/publish.py --rebuild-index   # indexだけ再生成
"""
import html as html_mod
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EXIT_KYUKAN = 2
MOUSHIOKURI_KEEP = 14
REQUIRED_KEYS = ("vol", "hantei", "daicho_line", "moushiokuri")
JST = timezone(timedelta(hours=9))

DAICHO_LINE_RE = re.compile(
    r"^vol\.(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$")
DATE_RE = re.compile(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|")

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>folio — AI編集部の日刊誌</title>
<meta property="og:title" content="folio">
<meta property="og:description" content="AI編集部が毎日発行するWeb雑誌。最新号はVOL.__LATEST_VOL__「__LATEST_TITLE__」">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root { --ink:#111; --paper:#FBFBF8; --desk:#D9D9D6; --rule:1px solid #111; }
*{box-sizing:border-box}
body{margin:0;padding:32px 0;background:var(--desk);color:var(--ink);font-family:"Noto Sans JP",sans-serif;-webkit-font-smoothing:antialiased}
.hanmen{width:390px;max-width:100%;margin:0 auto;background:var(--paper);box-shadow:0 0 24px rgba(0,0,0,.18);padding:16px 16px 32px}
.masthead{display:flex;justify-content:space-between;align-items:baseline;font-size:10px;letter-spacing:.18em;font-weight:700;border-bottom:var(--rule);padding-bottom:8px}
.masthead .logo{font-weight:900;font-size:13px;letter-spacing:.3em}
a{color:inherit;text-decoration:none}
.latest{display:block;border-bottom:var(--rule);padding:20px 0 16px}
.latest .label{font-size:10px;letter-spacing:.24em;font-weight:700}
.latest .no{font-weight:900;font-size:15px;letter-spacing:.12em;margin-top:8px}
.latest h1{margin:4px 0 8px;font-weight:900;font-size:44px;line-height:1.1;font-feature-settings:"palt"}
.latest .meta{font-size:11px;letter-spacing:.08em}
.latest .summary{font-size:12px;line-height:1.9;margin-top:8px}
.archive{list-style:none;margin:0;padding:0}
.archive li{border-bottom:1px solid rgba(17,17,17,.25)}
.archive a{display:flex;gap:10px;align-items:baseline;padding:10px 2px;font-size:12px}
.archive .no{font-weight:900;letter-spacing:.08em;flex:none}
.archive .ti{font-weight:700;flex:1}
.archive .dt{font-size:10px;letter-spacing:.06em}
.colophon{margin-top:24px;font-size:9px;letter-spacing:.08em;line-height:1.8}
</style>
</head>
<body>
<div class="hanmen">
  <header class="masthead"><span class="logo">folio</span><span>DAILY MAGAZINE</span></header>
  <a class="latest" href="./vol-__LATEST_VOL__.html">
    <div class="label">最新号</div>
    <div class="no">VOL.__LATEST_VOL__</div>
    <h1>__LATEST_TITLE__</h1>
    <div class="meta">__LATEST_DATE__ / __LATEST_GENRES__</div>
    <p class="summary">__LATEST_SUMMARY__</p>
  </a>
  <ul class="archive">
__ARCHIVE_ROWS__
  </ul>
  <p class="colophon">folio — AI編集部が毎日発行するWeb雑誌。<br>本誌の一部リンクはアフィリエイトプログラムを利用しており、リンク経由の購入等により発行元が収益を得ることがあります。</p>
</div>
</body>
</html>
"""


def parse_daicho(text: str) -> list[dict]:
    entries = []
    for line in text.splitlines():
        m = DAICHO_LINE_RE.match(line.strip())
        if m:
            entries.append({
                "vol": int(m.group(1)),
                "date": m.group(2),
                "title": m.group(3),
                "genres": m.group(4),
                "summary": m.group(5),
            })
    return entries


def render_index(entries: list[dict]) -> str:
    if not entries:
        raise SystemExit("[error] 台帳が空。indexを生成できない")
    e = html_mod.escape
    latest = entries[-1]
    rows = "\n".join(
        f'    <li><a href="./vol-{x["vol"]:03d}.html">'
        f'<span class="no">VOL.{x["vol"]:03d}</span>'
        f'<span class="ti">{e(x["title"])}</span>'
        f'<span class="dt">{e(x["date"])}</span></a></li>'
        for x in reversed(entries))
    return (INDEX_TEMPLATE
            .replace("__LATEST_VOL__", f"{latest['vol']:03d}")
            .replace("__LATEST_TITLE__", e(latest["title"]))
            .replace("__LATEST_DATE__", e(latest["date"]))
            .replace("__LATEST_GENRES__", e(latest["genres"]))
            .replace("__LATEST_SUMMARY__", e(latest["summary"]))
            .replace("__ARCHIVE_ROWS__", rows))


def update_moushiokuri(text: str, date_str: str, vol: int, message: str) -> str:
    parts = [p.strip() for p in re.split(r"[・\n]+", message) if p.strip()]
    body = "\n".join(f"- {p}" for p in parts)
    new_entry = f"## {date_str} (vol.{vol:03d} 校了時)\n{body}"
    chunks = re.split(r"\n(?=## )", text.strip())
    entries = [c.strip() for c in chunks if c.strip().startswith("## ")]
    entries.append(new_entry)
    entries = entries[-MOUSHIOKURI_KEEP:]
    return "# 申し送り\n\n" + "\n\n".join(entries) + "\n"


def rebuild_index(root: Path, daicho_text: str) -> None:
    issues = root / "issues"
    issues.mkdir(exist_ok=True)
    (issues / "index.html").write_text(render_index(parse_daicho(daicho_text)),
                                       encoding="utf-8")


def publish(root: Path, vol: int) -> int:
    desk = root / "desk" / f"vol-{vol:03d}"
    kouryou_path = desk / "07_kouryou.json"
    if not kouryou_path.exists():
        raise SystemExit(f"[error] {kouryou_path} が無い")
    kouryou = json.loads(kouryou_path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if k not in kouryou]
    if missing:
        raise SystemExit(f"[error] 07_kouryou.json に必須キーが無い: {missing}")

    hantei = kouryou["hantei"]
    if hantei == "休刊":
        print(f"[kyukan] vol.{vol:03d}: {kouryou.get('riyu', '(理由未記載)')}",
              file=sys.stderr)
        return EXIT_KYUKAN
    if hantei not in ("校了", "責了"):
        raise SystemExit(f"[error] 不明なhantei: {hantei}")

    gera = desk / "gera.html"
    if not gera.exists():
        raise SystemExit(f"[error] {gera} が無い")

    issues = root / "issues"
    issues.mkdir(exist_ok=True)
    shutil.copyfile(gera, issues / f"vol-{vol:03d}.html")

    daicho_path = root / "editorial" / "daicho.md"
    text = daicho_path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    text += kouryou["daicho_line"].strip() + "\n"
    daicho_path.write_text(text, encoding="utf-8")

    m = DATE_RE.search(kouryou["daicho_line"])
    date_str = m.group(1) if m else datetime.now(JST).date().isoformat()
    moushiokuri_path = root / "editorial" / "moushiokuri.md"
    existing = (moushiokuri_path.read_text(encoding="utf-8")
                if moushiokuri_path.exists() else "# 申し送り\n")
    moushiokuri_path.write_text(
        update_moushiokuri(existing, date_str, vol, kouryou["moushiokuri"]),
        encoding="utf-8")

    rebuild_index(root, text)
    print(f"[ok] vol.{vol:03d} 発行。台帳追記・申し送り更新・index再生成済み")
    return 0


def main(argv: list[str]) -> None:
    root = Path(__file__).resolve().parent.parent
    if not argv:
        raise SystemExit("usage: publish.py <vol> | publish.py --rebuild-index")
    if argv[0] == "--rebuild-index":
        rebuild_index(root, (root / "editorial" / "daicho.md").read_text(encoding="utf-8"))
        print("[ok] index.html を再生成")
        return
    sys.exit(publish(root, int(argv[0])))


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_publish.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_publish.py scripts/publish.py
git commit -m "feat: 発行スクリプトを追加(台帳追記・申し送り・index生成)"
```

---

### Task 8: 統合テスト + 初期 index.html 生成

**Files:**
- Create: `tests/test_integration_vol002.py`
- Create: `issues/index.html`(スクリプトで生成)

- [ ] **Step 1: 統合テストを書く** — `tests/test_integration_vol002.py`

```python
"""工程5→7前半→9 の決定論チェーンを vol.002 実データで通す統合テスト"""
import json
from pathlib import Path

import kousei_machine
import link_decorator
import publish

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vol-002"

DAICHO_V1 = """# folio 特集台帳

vol.001 | 2026-07-19 | 空港の時間 | music,film,architecture | 試し刷
"""


def test_full_deterministic_chain(tmp_path, monkeypatch):
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    monkeypatch.delenv("FOLIO_CHECK_URLS", raising=False)

    # 工程5: リンク加工 — 出力が既知の05と一致する
    goudata_path = tmp_path / "05_goudata.json"
    link_decorator.main(str(FIXTURES / "03_genko.json"), str(goudata_path))
    got = json.loads(goudata_path.read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "05_goudata.json").read_text(encoding="utf-8"))
    assert got["items"] == expected["items"]

    # 工程7前半: 機械校正 — 全項目pass
    machine_path = tmp_path / "machine.json"
    kousei_machine.main(str(goudata_path), str(FIXTURES / "vol-002.html"),
                        str(machine_path))
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    assert machine["genko_match"] is True
    assert machine["links_ok"] is True
    assert machine["html_ok"] is True

    # 工程9: 発行(vol.002の実judgmentは責了)
    root = tmp_path / "repo"
    (root / "editorial").mkdir(parents=True)
    (root / "editorial" / "daicho.md").write_text(DAICHO_V1, encoding="utf-8")
    desk = root / "desk" / "vol-002"
    desk.mkdir(parents=True)
    (desk / "07_kouryou.json").write_text(
        (FIXTURES / "07_kouryou.json").read_text(encoding="utf-8"), encoding="utf-8")
    (desk / "gera.html").write_text(
        (FIXTURES / "vol-002.html").read_text(encoding="utf-8"), encoding="utf-8")

    assert publish.publish(root, 2) == 0

    assert (root / "issues" / "vol-002.html").exists()
    index = (root / "issues" / "index.html").read_text(encoding="utf-8")
    assert "VOL.002" in index
    assert "氷" in index
    moushiokuri = (root / "editorial" / "moushiokuri.md").read_text(encoding="utf-8")
    assert "vol.002 校了時" in moushiokuri
```

- [ ] **Step 2: 統合テストを実行**

Run: `python -m pytest tests/test_integration_vol002.py -v`
Expected: 1 passed(失敗したらスクリプト側のバグ。テストを弄って合わせない)

- [ ] **Step 3: 初期 index.html を生成**(既刊2号の台帳から)

```bash
python scripts/publish.py --rebuild-index
```

- [ ] **Step 4: 生成物を検証**

```bash
grep -c "vol-00" issues/index.html   # 3以上(最新号リンク+アーカイブ2行)
grep "氷" issues/index.html          # 最新号としてVOL.002が出ること
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration_vol002.py issues/index.html
git commit -m "test: vol.002実データによる決定論チェーン統合テストと初期indexを追加"
```

---

### Task 9: CI ワークフロー(test.yml)と全テスト確認

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: test.yml を作成**

```yaml
name: test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install pytest pytest-cov
      - run: python -m pytest tests/ -v --cov=scripts --cov-report=term-missing --cov-fail-under=80
```

- [ ] **Step 2: ローカルで同じコマンドを実行してカバレッジを確認**

Run: `pip install pytest pytest-cov && python -m pytest tests/ -v --cov=scripts --cov-report=term-missing --cov-fail-under=80`
Expected: 全テスト passed、カバレッジ 80% 以上。不足していたら不足行(`term-missing` 表示)のテストを追加する

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: pytestワークフローを追加(カバレッジ80%ゲート)"
```

---

### Task 10: deploy-pages.yml と daily-issue.yml

**Files:**
- Create: `.github/workflows/deploy-pages.yml`
- Create: `.github/workflows/daily-issue.yml`

- [ ] **Step 1: deploy-pages.yml を作成**(手動初回公開用+日次からの workflow_call 用)

```yaml
name: deploy-pages

on:
  workflow_dispatch:
  workflow_call:

permissions:
  pages: write
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main   # 日次ジョブがpushした最新を確実に拾う
      - uses: actions/upload-pages-artifact@v3
        with:
          path: issues
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: daily-issue.yml を作成**

注意点:
- cron はUTC。`0 15 * * *` = JST 0:00
- 1 LLM工程 = 1 つの claude-code-action ステップ。モデルは全工程 Haiku
- 各LLM工程の直後に jq による「検品」ステップを置き、出力ファイルの存在と必須キーを機械検証する
- 分岐(4b改稿・8b責了)は jq で判定フィールドを読む。LLMに分岐判断させない

```yaml
name: daily-issue

on:
  schedule:
    - cron: "0 15 * * *"   # JST 0:00
  workflow_dispatch:

concurrency:
  group: daily-issue
  cancel-in-progress: false

jobs:
  issue:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    permissions:
      contents: write
      issues: write
    outputs:
      hantei: ${{ steps.kouryou_check.outputs.hantei }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 工程0 号数決定とシード生成
        id: seed
        run: python scripts/seed.py >> "$GITHUB_OUTPUT"

      - name: 工程1 企画(editor-in-chief)
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の企画を立てて。
            起点シードは desk/vol-${{ steps.seed.outputs.nnn }}/seed.md を読むこと。
            出力は desk/vol-${{ steps.seed.outputs.nnn }}/01_kikaku.json へ。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程1 検品
        run: jq -e '.title and .genres' "desk/vol-${{ steps.seed.outputs.nnn }}/01_kikaku.json"

      - name: 工程2 リサーチ(researcher)
        uses: anthropics/claude-code-action@v1
        env:
          RAKUTEN_APP_ID: ${{ secrets.RAKUTEN_APP_ID }}
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          TMDB_API_KEY: ${{ secrets.TMDB_API_KEY }}
          GOOGLE_PLACES_API_KEY: ${{ secrets.GOOGLE_PLACES_API_KEY }}
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の候補を集めて。
            desk/vol-${{ steps.seed.outputs.nnn }}/01_kikaku.json の発注に従うこと。
            URL検証には scripts/verify_links.py を使うこと。
            出力は desk/vol-${{ steps.seed.outputs.nnn }}/02_kouho.json へ。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程2 検品
        run: jq -e '.genres | length > 0' "desk/vol-${{ steps.seed.outputs.nnn }}/02_kouho.json"

      - name: 工程3 執筆(genre-editor)
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の原稿を書いて。
            入力は desk/vol-${{ steps.seed.outputs.nnn }}/ の 01_kikaku.json と 02_kouho.json。
            出力は desk/vol-${{ steps.seed.outputs.nnn }}/03_genko.json へ。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程3 検品
        run: jq -e '.issue and (.items | length > 0)' "desk/vol-${{ steps.seed.outputs.nnn }}/03_genko.json"

      - name: 工程4 校閲(koetsu)
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の校閲をして。
            入力は desk/vol-${{ steps.seed.outputs.nnn }}/ の 01〜03 のJSON。
            出力は desk/vol-${{ steps.seed.outputs.nnn }}/04_koetsu.json へ。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程4 判定読取
        id: koetsu_check
        run: echo "verdict=$(jq -r '.verdict' "desk/vol-${{ steps.seed.outputs.nnn }}/04_koetsu.json")" >> "$GITHUB_OUTPUT"

      - name: 工程4b 改稿(fix_required時のみ)
        if: steps.koetsu_check.outputs.verdict == 'fix_required'
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の校閲対応をして(改稿モード)。
            desk/vol-${{ steps.seed.outputs.nnn }}/04_koetsu.json の指摘に従い、
            desk/vol-${{ steps.seed.outputs.nnn }}/03_genko.json を更新すること。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程5 リンク加工(スクリプト)
        env:
          RAKUTEN_AFF_PARAM: ${{ secrets.RAKUTEN_AFF_PARAM }}
        run: >
          python scripts/link_decorator.py
          "desk/vol-${{ steps.seed.outputs.nnn }}/03_genko.json"
          "desk/vol-${{ steps.seed.outputs.nnn }}/05_goudata.json"

      - name: 工程6 組版(art-director)
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の誌面を組んで。
            入力は desk/vol-${{ steps.seed.outputs.nnn }}/05_goudata.json。
            出力は desk/vol-${{ steps.seed.outputs.nnn }}/gera.html へ。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程6 検品
        run: |
          test -s "desk/vol-${{ steps.seed.outputs.nnn }}/gera.html"
          ! grep -q "<script" "desk/vol-${{ steps.seed.outputs.nnn }}/gera.html"

      - name: 工程7 機械校正(スクリプト・URL実測)
        env:
          FOLIO_CHECK_URLS: "1"
        run: >
          python scripts/kousei_machine.py
          "desk/vol-${{ steps.seed.outputs.nnn }}/05_goudata.json"
          "desk/vol-${{ steps.seed.outputs.nnn }}/gera.html"
          "desk/vol-${{ steps.seed.outputs.nnn }}/machine.json"

      - name: 工程7 校正(kousei)
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の校正をして。
            機械チェックは実行済みで desk/vol-${{ steps.seed.outputs.nnn }}/machine.json にある(再実行不要)。
            ゲラは desk/vol-${{ steps.seed.outputs.nnn }}/gera.html、照合元は 05_goudata.json。
            出力は desk/vol-${{ steps.seed.outputs.nnn }}/06_kousei.json へ。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程7 検品
        run: jq -e '.machine' "desk/vol-${{ steps.seed.outputs.nnn }}/06_kousei.json"

      - name: 工程8 校了(editor-in-chief)
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の校了判定をして。
            desk/vol-${{ steps.seed.outputs.nnn }}/ の gera.html と 01〜06 を読み、
            desk/vol-${{ steps.seed.outputs.nnn }}/07_kouryou.json を出力すること。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程8 判定読取
        id: kouryou_check
        run: echo "hantei=$(jq -r '.hantei' "desk/vol-${{ steps.seed.outputs.nnn }}/07_kouryou.json")" >> "$GITHUB_OUTPUT"

      - name: 工程8b 責了対応(責了時のみ)
        if: steps.kouryou_check.outputs.hantei == '責了'
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: >-
            vol.${{ steps.seed.outputs.vol }} の責了対応をして(修正モード)。
            desk/vol-${{ steps.seed.outputs.nnn }}/07_kouryou.json の sekiryo_shiji を
            desk/vol-${{ steps.seed.outputs.nnn }}/gera.html に適用すること。
          claude_args: "--model claude-haiku-4-5-20251001 --allowedTools Bash,Read,Write,Edit,Glob,Grep"

      - name: 工程9 発行(スクリプト)
        if: steps.kouryou_check.outputs.hantei != '休刊'
        run: python scripts/publish.py "${{ steps.seed.outputs.vol }}"

      - name: 休刊Issueを起票
        if: steps.kouryou_check.outputs.hantei == '休刊'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          riyu=$(jq -r '.riyu // "理由未記載"' "desk/vol-${{ steps.seed.outputs.nnn }}/07_kouryou.json")
          gh issue create --title "休刊: vol.${{ steps.seed.outputs.vol }} ($(TZ=Asia/Tokyo date +%F))" --body "$riyu"

      - name: 工程失敗Issueを起票
        if: failure()
        env:
          GH_TOKEN: ${{ github.token }}
        run: >-
          gh issue create
          --title "工程失敗: vol.${{ steps.seed.outputs.vol || '?' }} ($(TZ=Asia/Tokyo date +%F))"
          --body "daily-issue ワークフローが失敗した。ログ: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"

      - name: コミット&プッシュ(desk/は結果に関わらず残す)
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A desk editorial issues
          if git diff --cached --quiet; then
            echo "変更なし"
          else
            git commit -m "issue: $(TZ=Asia/Tokyo date +%F) vol.${{ steps.seed.outputs.vol || 'unknown' }}"
            git push
          fi

  deploy:
    needs: issue
    if: needs.issue.outputs.hantei == '校了' || needs.issue.outputs.hantei == '責了'
    permissions:
      pages: write
      id-token: write
      contents: read
    uses: ./.github/workflows/deploy-pages.yml
```

- [ ] **Step 3: YAML の構文検証**

```bash
pip install pyyaml
python -c "
import yaml
for f in ['.github/workflows/test.yml', '.github/workflows/deploy-pages.yml', '.github/workflows/daily-issue.yml']:
    yaml.safe_load(open(f))
    print(f, 'OK')
"
```

Expected: 3 ファイルとも OK

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy-pages.yml .github/workflows/daily-issue.yml
git commit -m "ci: 日次発行パイプラインとPagesデプロイのワークフローを追加"
```

---

### Task 11: セットアップ手順の README 追記と最終検証

**Files:**
- Modify: `README.md`(セットアップ節を追記)

- [ ] **Step 1: README.md の「## 開発」の前にセットアップ節を追記**

````markdown
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
````

- [ ] **Step 2: 全テストを最終実行**

Run: `python -m pytest tests/ -v --cov=scripts --cov-fail-under=80`
Expected: 全テスト passed、カバレッジゲート通過

- [ ] **Step 3: リポジトリ全体の整合を確認**

```bash
ls editorial scripts issues .claude/skills .github/workflows tests
git status   # クリーンであること(未コミットの取りこぼしがない)
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: セットアップ手順(Secrets・Pages・初回公開)を追記"
```

---

## 実装後の手動作業(ユーザーが行う)

コードでは完結しない作業。実装完了後にユーザーへ案内すること:

1. GitHub に push(リモート未設定なら `gh repo create` から)
2. Secrets 7 種を登録(README のセットアップ節参照)
3. Settings → Pages → Source を「GitHub Actions」に変更
4. Actions タブから `deploy-pages` を手動実行(初回公開)
5. Actions タブから `daily-issue` を手動実行(vol.003 のリハーサル)し、desk/ の中間生成物と発行結果を確認
