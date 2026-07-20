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

REL_ATTR_RE = re.compile(r'<a\b[^>]*\brel="([^"]*)"[^>]*>')
HREF_SRC_RE = re.compile(r'(?:href|src)="([^"]*)"')
SAFE_SCHEME_RE = re.compile(r'^https?://', re.IGNORECASE)
ANY_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.\-]*:')


def _count_sponsored_rel(html: str) -> int:
    """rel属性値がsponsoredとnoopenerの両方を含む<a>タグの数を数える(属性順に依存しない)。"""
    count = 0
    for rel_value in re.findall(REL_ATTR_RE, html):
        tokens = rel_value.split()
        if "sponsored" in tokens and "noopener" in tokens:
            count += 1
    return count


def _find_unsafe_schemes(html: str) -> list[str]:
    """href/srcがhttp(s)・相対パス・#のいずれでもない値を列挙する(javascript:/data:/mailto:等)。"""
    unsafe = []
    for value in re.findall(HREF_SRC_RE, html):
        if SAFE_SCHEME_RE.match(value):
            continue
        if value.startswith("#"):
            continue
        if not ANY_SCHEME_RE.match(value):
            continue  # スキームを持たない相対パス
        unsafe.append(value)
    return unsafe


def build_machine(d: dict, html: str, check_urls: bool) -> dict:
    texts = [("lead", d["issue"]["lead"])] + [
        (f"items[{i}].essay", it["essay"]) for i, it in enumerate(d["items"])
    ]
    genko = {name: ((t in html) or (html_mod.escape(t) in html)) for name, t in texts}

    links = [l for it in d["items"] for l in it["links"]]
    link_present = {l["url"]: (l["url"] in html) for l in links}
    n_sp = sum(1 for l in links if l["sponsored"])
    rel_ok = _count_sponsored_rel(html) == n_sp
    pr_ok = html.count("[PR]") == n_sp

    ext_hrefs = set(re.findall(r'(?:href|src)="(https?://[^"]+)"', html))
    known = {l["url"] for l in links}
    unknown = []
    for u in ext_hrefs:
        host = re.match(r"https?://([^/]+)", u).group(1)
        if u not in known and host not in ALLOWED_RESOURCE_HOSTS:
            unknown.append(u)

    unsafe_schemes = sorted(set(_find_unsafe_schemes(html)))

    if check_urls:
        url_status = [{"url": l["url"], "status": verify_links.check_url(l["url"])}
                      for l in links]
    else:
        url_status = "skip(FOLIO_CHECK_URLS未設定)"

    return {
        "genko_match": all(genko.values()),
        "genko_detail": genko,
        "links_ok": all(link_present.values()) and not unknown and not unsafe_schemes,
        "links_detail": {"present": link_present, "unknown_external": sorted(unknown),
                          "unsafe_schemes": unsafe_schemes},
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
