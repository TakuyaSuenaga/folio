#!/usr/bin/env python3
"""folio 工程5: リンク加工(決定論・LLM禁止工程)
03_genko.json を読み、ドメイン→アフィリエイト対応表を適用して
sponsored を確定し、05_goudata.json を出力する。

- 対応表にあるドメイン: sponsored=True。AFF IDが環境変数にあればURLへ付与
- 対応表にないドメイン: sponsored=False、URL無改変
- AFF ID未設定時はURLを改変しない(壊れたパラメータを配らない)
"""
import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

AFF_TABLE = {
    "books.rakuten.co.jp": {"env": "RAKUTEN_AFF_PARAM", "sponsored": True},
    # "px.a8.net": {"env": "A8_AFF_PARAM", "sponsored": True},  # VOD系は本番で追加
}


def decorate(link: dict) -> dict:
    out = dict(link)
    out.pop("kind", None)
    host = urllib.parse.urlparse(link["url"]).netloc
    rule = AFF_TABLE.get(host)
    if not rule:
        out["sponsored"] = False
        return out
    out["sponsored"] = rule["sponsored"]
    aff = os.environ.get(rule["env"], "")
    if not aff:
        print(f"[warn] {rule['env']} 未設定: {host} はsponsored扱いのままURL無改変", file=sys.stderr)
        return out

    k, sep, v = aff.partition("=")
    if not sep or not k:
        print(f"[warn] {rule['env']} の形式が不正(key=value形式でない): "
              f"{host} はsponsored扱いのままURL無改変", file=sys.stderr)
        return out

    u = urllib.parse.urlparse(link["url"])
    q = dict(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
    q[k] = v
    out["url"] = urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q)))
    return out


def main(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as f:
        genko = json.load(f)
    goudata = {
        "issue": genko["issue"],
        "items": [
            {**{k: v for k, v in item.items() if k != "links"},
             "links": [decorate(l) for l in item.get("links", [])]}
            for item in genko["items"]
        ],
    }
    if "colophon" in genko:
        goudata["colophon"] = genko["colophon"]
    goudata["decorated_at"] = datetime.now(JST).date().isoformat()
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(goudata, f, ensure_ascii=False, indent=2)
    n_sp = sum(1 for i in goudata["items"] for l in i["links"] if l["sponsored"])
    print(f"[ok] {dst} 生成。sponsoredリンク {n_sp} 件")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
