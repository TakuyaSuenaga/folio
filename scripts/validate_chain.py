#!/usr/bin/env python3
"""02候補と03原稿の実在チェーンを決定論的に検証する。

usage: python scripts/validate_chain.py 01_kikaku.json 02_kouho.json 03_genko.json
成功時はGitHub Actions output形式で has_items=true/false をstdoutへ出す。
"""
import json
import sys
from pathlib import Path


TRANSFER_FIELDS = ("title", "creator", "year", "publisher", "meta", "image", "links")
REQUIRED_CANDIDATE_FIELDS = ("cand_id", "source_api", "source_id", "verify")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSONのルートがobjectではない")
    return value


def validate(kikaku: dict, kouho: dict, genko: dict) -> list[str]:
    errors = []
    items = genko.get("items")
    if not isinstance(items, list):
        return ["03.itemsが配列ではない"]

    expected_vol = kikaku.get("vol")
    if kouho.get("vol") != expected_vol:
        errors.append("01.volと02.volが一致しない")
    issue = genko.get("issue")
    if not isinstance(issue, dict) or issue.get("vol") != expected_vol:
        errors.append("03.issue.volが01.volと一致しない")
    for source, target, label in (
        ("date", "date", "date"),
        ("title", "title", "title"),
        ("lead_draft", "lead", "lead"),
    ):
        if not isinstance(issue, dict) or issue.get(target) != kikaku.get(source):
            errors.append(f"03.issue.{label}が01からの転記と一致しない")

    candidates = {}
    for group in kouho.get("genres", []):
        if not isinstance(group, dict):
            errors.append("02.genresにobjectでない要素がある")
            continue
        genre = group.get("genre")
        for candidate in group.get("candidates", []):
            if not isinstance(candidate, dict):
                errors.append(f"02の{genre}候補にobjectでない要素がある")
                continue
            missing = [k for k in REQUIRED_CANDIDATE_FIELDS if k not in candidate]
            if missing:
                errors.append(f"02候補({candidate.get('cand_id')})の必須項目欠落: {missing}")
                continue
            key = candidate["cand_id"]
            if key in candidates:
                errors.append(f"02でcand_idが重複: {key}")
            candidates[key] = (genre, candidate)

    seen = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"03.items[{index}]がobjectではない")
            continue
        cand_id = item.get("cand_id")
        if not cand_id or cand_id not in candidates:
            errors.append(f"03.items[{index}]のcand_idが02に存在しない: {cand_id!r}")
            continue
        if cand_id in seen:
            errors.append(f"03でcand_idが重複: {cand_id}")
        seen.add(cand_id)
        genre, candidate = candidates[cand_id]
        if item.get("genre") != genre:
            errors.append(f"03.items[{index}]のgenreが02と一致しない")
        verify = candidate.get("verify")
        if not isinstance(verify, dict) or verify.get("id_confirmed") is not True:
            errors.append(f"候補({cand_id})の実在確認が完了していない")
        status = verify.get("url_status") if isinstance(verify, dict) else None
        if not isinstance(status, int) or status >= 400:
            errors.append(f"候補({cand_id})のURL生存確認が成功していない")
        for field in TRANSFER_FIELDS:
            if field in candidate and item.get(field) != candidate[field]:
                errors.append(f"03.items[{index}].{field}が02から改変されている")
            if field not in candidate and field in item:
                defaults = {"year": None, "publisher": "", "meta": {},
                            "image": None, "links": []}
                if field not in defaults or item[field] != defaults[field]:
                    errors.append(f"03.items[{index}].{field}が02にないのに追加されている")
    return errors


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        raise SystemExit("usage: validate_chain.py 01_kikaku.json 02_kouho.json 03_genko.json")
    try:
        kikaku, kouho, genko = (_load(path) for path in argv)
        errors = validate(kikaku, kouho, genko)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        raise SystemExit(f"[error] 実在チェーン検証不能: {e}") from None
    if errors:
        raise SystemExit("[error] 実在チェーン検証失敗:\n- " + "\n- ".join(errors))
    print(f"has_items={'true' if genko['items'] else 'false'}")
    print(f"[ok] 実在チェーン: 採用{len(genko['items'])}件", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
