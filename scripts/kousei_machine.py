#!/usr/bin/env python3
"""folio 工程7(前半): 校正の機械チェック(決定論)

05_goudata.json とゲラHTMLを照合し、machine結果JSONを出力する。
- 原稿一致(lead/essayの完全一致包含)
- リンク照合(全URL存在、sponsoredのrel/[PR]、05に無い外部hrefの検出)
- HTML健全性(lang/h1/script不在/viewport/OGP/外部リソース許可制)
- 規定文言(奥付のアフィリエイト包括表記)
- リンク死活: 環境変数 FOLIO_CHECK_URLS=1 のときのみ実測(CI用)
"""
import html as html_mod
import json
import os
import re
import sys

import verify_links

OKUZUKE = "本誌の一部リンクはアフィリエイトプログラムを利用しており、リンク経由の購入等により発行元が収益を得ることがあります。"
ALLOWED_RESOURCE_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com", "tshop.r10s.jp"}

# 属性は大文字・シングルクォートでも等価に解釈されるため両対応で拾う(取りこぼしはfail-openになる)
REL_ATTR_RE = re.compile(r'<a\b[^>]*\brel\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.IGNORECASE)
HREF_SRC_RE = re.compile(r'(?:href|src)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.IGNORECASE)
SAFE_SCHEME_RE = re.compile(r'^https?://', re.IGNORECASE)
ANY_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.\-]*:')
# タグ内のインラインイベントハンドラ(onerror= 等。scriptタグを使わないJS実行経路)
EVENT_HANDLER_RE = re.compile(r'<[^>]*?\b(on[a-z]+)\s*=', re.IGNORECASE)
HOST_RE = re.compile(r'https?://([^/]+)', re.IGNORECASE)


def _attr_values(html: str) -> list[str]:
    """href/src属性の値を、引用符の種類・属性名の大文字小文字に依らず列挙する。"""
    return [dq or sq for dq, sq in HREF_SRC_RE.findall(html)]


def _normalize_url(value: str) -> str:
    """属性値のHTMLエスケープ(&amp;)だけを狭く復号してURL照合に使う。
    html.unescapeはセミコロン無しのレガシー実体(&para等)まで復号しURLを壊すため使わない。"""
    return value.replace("&amp;", "&")


def _count_sponsored_rel(html: str) -> int:
    """rel属性値がsponsoredとnoopenerの両方を含む<a>タグの数を数える(属性順に依存しない)。"""
    count = 0
    for dq, sq in REL_ATTR_RE.findall(html):
        tokens = (dq or sq).split()
        if "sponsored" in tokens and "noopener" in tokens:
            count += 1
    return count


def _find_unsafe_schemes(values: list[str]) -> list[str]:
    """href/srcがhttp(s)・相対パス・#のいずれでもない値を列挙する(javascript:/data:/mailto:等)。
    ブラウザ挙動に合わせ、実体参照の復号とタブ・改行の除去をしてからスキームを判定する。"""
    unsafe = []
    for value in values:
        decoded = re.sub(r"[\t\r\n]", "", html_mod.unescape(value))
        if SAFE_SCHEME_RE.match(decoded):
            continue
        if decoded.startswith("#"):
            continue
        if not ANY_SCHEME_RE.match(decoded):
            continue  # スキームを持たない相対パス
        unsafe.append(value)
    return unsafe


def _find_unknown_external(attr_values: list[str], known: set[str]) -> list[str]:
    """既知URL(links/image)にも許可ホストにも該当しない外部参照を列挙する。"""
    ext = {_normalize_url(v) for v in attr_values if SAFE_SCHEME_RE.match(v)}
    unknown = []
    for u in sorted(ext):
        if u in known:
            continue
        m = HOST_RE.match(u)
        host = m.group(1).lower() if m else None
        if host not in ALLOWED_RESOURCE_HOSTS:
            unknown.append(u)
    return unknown


def build_machine(d: dict, html: str, check_urls: bool) -> dict:
    texts = [("lead", d["issue"]["lead"])] + [
        (f"items[{i}].essay", it["essay"]) for i, it in enumerate(d["items"])
    ]
    genko = {name: ((t in html) or (html_mod.escape(t) in html)) for name, t in texts}

    links = [l for it in d["items"] for l in it["links"]]
    attr_values = _attr_values(html)
    # 生のURL・正しく&amp;エスケープされたhrefのどちらで組まれても照合できるようにする
    normalized_attrs = {_normalize_url(v) for v in attr_values}
    link_present = {l["url"]: (l["url"] in html or l["url"] in normalized_attrs)
                    for l in links}
    n_sp = sum(1 for l in links if l["sponsored"])
    rel_ok = _count_sponsored_rel(html) == n_sp
    pr_ok = html.count("[PR]") == n_sp

    known = {l["url"] for l in links}
    # goudataの image.url も許可済み外部リソースとして通す。実在チェーンでリサーチが
    # 採用した画像(openBD書影・iTunesジャケット・Places写真)であり、ホストを直書き
    # せずJSONに載った事実で許可する
    known |= {it["image"]["url"] for it in d["items"]
              if isinstance(it.get("image"), dict) and it["image"].get("url")}
    unknown = _find_unknown_external(attr_values, known)

    unsafe_schemes = sorted(set(_find_unsafe_schemes(attr_values)))
    event_handlers = sorted({m.lower() for m in EVENT_HANDLER_RE.findall(html)})

    if check_urls:
        url_status = [{"url": l["url"], "status": verify_links.check_url(l["url"])}
                      for l in links]
    else:
        url_status = "skip(FOLIO_CHECK_URLS未設定)"

    return {
        "genko_match": all(genko.values()),
        "genko_detail": genko,
        "links_ok": (all(link_present.values()) and not unknown
                     and not unsafe_schemes and not event_handlers),
        "links_detail": {"present": link_present, "unknown_external": unknown,
                          "unsafe_schemes": unsafe_schemes,
                          "event_handlers": event_handlers},
        "pr_labels_ok": rel_ok and pr_ok,
        "html_ok": all([
            'lang="ja"' in html,
            len(re.findall(r"<h1", html, re.IGNORECASE)) == 1,
            re.search(r"<script", html, re.IGNORECASE) is None,
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
