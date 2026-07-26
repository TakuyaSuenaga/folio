#!/usr/bin/env python3
"""LLMの選定・原稿と01/02を合成し、転記ミスの起こらない03を生成する。

LLMが責任を持つのは cand_id / sentei_riyu / essay だけである。書誌・画像・リンクと
issue情報は信頼できる上流JSONから必ず再構築する。不正なitemは記事単位で落とし、
残った記事があれば部分成功として続行する。
"""
import json
import sys


COPY_FIELDS = ("title", "creator", "year", "publisher", "meta", "image", "links")


def hydrate(kikaku: dict, kouho: dict, draft: dict) -> tuple[dict, list[dict]]:
    candidates = {}
    for group in kouho.get("genres", []):
        for candidate in group.get("candidates", []):
            if isinstance(candidate, dict) and candidate.get("cand_id"):
                candidates[candidate["cand_id"]] = (group.get("genre"), candidate)

    items = []
    dropped = []
    seen = set()
    for index, raw in enumerate(draft.get("items", [])):
        cand_id = raw.get("cand_id") if isinstance(raw, dict) else None
        reason = None
        if not isinstance(raw, dict):
            reason = "itemがobjectではない"
        elif not cand_id or cand_id not in candidates:
            reason = "cand_idが02に存在しない"
        elif cand_id in seen:
            reason = "cand_idが重複"
        else:
            genre, candidate = candidates[cand_id]
            verify = candidate.get("verify")
            status = verify.get("url_status") if isinstance(verify, dict) else None
            if not isinstance(verify, dict) or verify.get("id_confirmed") is not True:
                reason = "実在確認が未完了"
            elif not isinstance(status, int) or status >= 400:
                reason = "URL生存確認が未完了"
            elif not isinstance(raw.get("essay"), str) or not raw["essay"].strip():
                reason = "essayが空"
            elif not isinstance(raw.get("sentei_riyu"), str):
                reason = "sentei_riyuがない"
            else:
                item = {
                    "genre": genre,
                    "cand_id": cand_id,
                    "sentei_riyu": raw["sentei_riyu"],
                    **{field: candidate.get(field, default)
                       for field, default in (
                           ("title", ""), ("creator", ""), ("year", None),
                           ("publisher", ""), ("meta", {}), ("links", []))
                       },
                    "essay": raw["essay"],
                }
                if candidate.get("image"):
                    item["image"] = candidate["image"]
                items.append(item)
                seen.add(cand_id)
        if reason:
            dropped.append({"index": index, "cand_id": cand_id, "reason": reason})

    issue = {
        "vol": kikaku["vol"],
        "date": kikaku["date"],
        "title": kikaku["title"],
        "lead": kikaku["lead_draft"],
    }
    if kikaku.get("spot_color"):
        issue["spot_color"] = kikaku["spot_color"]
    result = {"issue": issue, "items": items}
    for optional in ("colophon", "revision_note"):
        if optional in draft:
            result[optional] = draft[optional]
    return result, dropped


def main(argv: list[str]) -> None:
    if len(argv) != 4:
        raise SystemExit(
            "usage: hydrate_genko.py 01_kikaku.json 02_kouho.json draft.json 03_genko.json")
    with open(argv[0], encoding="utf-8") as f:
        kikaku = json.load(f)
    with open(argv[1], encoding="utf-8") as f:
        kouho = json.load(f)
    with open(argv[2], encoding="utf-8") as f:
        draft = json.load(f)
    result, dropped = hydrate(kikaku, kouho, draft)
    with open(argv[3], "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    for item in dropped:
        print(f"[warn] itemを除外: {item}", file=sys.stderr)
    print(f"[ok] 03を正規化: 採用{len(result['items'])}件・除外{len(dropped)}件")


if __name__ == "__main__":
    main(sys.argv[1:])
