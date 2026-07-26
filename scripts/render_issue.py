#!/usr/bin/env python3
"""05確定データとADのデザイン設定から安全な自己完結HTMLを決定論的に生成する。"""
import html
import json
import re
import sys

from kousei_machine import OKUZUKE


ALLOWED_LAYOUTS = {"type", "grid", "vertical"}
ALLOWED_COLUMNS = {1, 2}
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_design(raw: object, fallback_color: str = "#1740C8") -> dict:
    if not isinstance(raw, dict):
        raw = {}
    color = raw.get("spot_color", fallback_color)
    if not isinstance(color, str) or not HEX_COLOR_RE.fullmatch(color):
        color = fallback_color if HEX_COLOR_RE.fullmatch(fallback_color) else "#1740C8"
    layout = raw.get("cover_layout", "type")
    columns = raw.get("columns", 1)
    return {
        "spot_color": color,
        "cover_layout": layout if layout in ALLOWED_LAYOUTS else "type",
        "columns": columns if columns in ALLOWED_COLUMNS else 1,
        "reverse_data": raw.get("reverse_data") is True,
    }


def _metadata_rows(item: dict) -> list[tuple[str, object]]:
    rows = [("題名", item.get("title")), ("作者", item.get("creator")),
            ("年", item.get("year")), ("版元", item.get("publisher"))]
    rows.extend((str(k), v) for k, v in item.get("meta", {}).items())
    return [(label, value) for label, value in rows if value not in (None, "", [], {})]


def render(goudata: dict, design_raw: dict, lead_final: str | None = None) -> str:
    e = html.escape
    issue = goudata["issue"]
    design = normalize_design(design_raw, issue.get("spot_color", "#1740C8"))
    lead = lead_final or issue["lead"]
    vol = int(issue["vol"])
    title = str(issue["title"])
    sections = []
    for index, item in enumerate(goudata["items"], 1):
        image = ""
        if isinstance(item.get("image"), dict) and item["image"].get("url"):
            alt = item["image"].get("alt") or f"{item.get('title', '')} の画像"
            credits = "".join(
                f'<a href="{e(a.get("uri", ""), quote=True)}" rel="noopener">'
                f'{e(a.get("name", ""))}</a>'
                for a in item["image"].get("attributions", []) if a.get("uri"))
            image = (
                f'<figure><img src="{e(item["image"]["url"], quote=True)}" alt="{e(alt)}">'
                f'{f"<figcaption>写真: {credits}</figcaption>" if credits else ""}</figure>')
        rows = "".join(
            f"<tr><th>{e(label)}</th><td>{e(str(value))}</td></tr>"
            for label, value in _metadata_rows(item))
        links = "".join(
            f'<a href="{e(link["url"], quote=True)}" '
            f'rel="{"sponsored " if link.get("sponsored") else ""}noopener">'
            f'{e(link.get("label", "リンク"))}{" [PR]" if link.get("sponsored") else ""}</a>'
            for link in item.get("links", []))
        if links:
            rows += f"<tr><th>入手</th><td>{links}</td></tr>"
        sections.append(f"""
<section class="item">
  <div class="genre">{e(str(item.get("genre", "")).upper())}</div>
  <h2>{e(str(item.get("title", "")))}</h2>
  {image}
  <p class="essay">{e(item["essay"])}</p>
  <table class="data{" reverse" if design["reverse_data"] else ""}">{rows}</table>
  <div class="folio"><span>folio — {e(title)}</span><span>{vol:03d} — {index:02d}</span></div>
</section>""")
    powered = ("<p>Powered by Google</p>" if any(
        isinstance(item.get("image"), dict)
        and item["image"].get("source") == "google-places"
        for item in goudata["items"]) else "")
    colophon = e(str(goudata.get("colophon", {}).get("note", "")))
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VOL.{vol:03d} {e(title)} — folio</title>
<meta property="og:title" content="VOL.{vol:03d} {e(title)}">
<meta property="og:description" content="{e(lead[:80], quote=True)}">
<meta property="og:type" content="article">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root{{--spot:{design["spot_color"]};--ink:#111;--paper:#fbfbf8;--desk:#d9d9d6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--desk);color:var(--ink);font-family:"Noto Sans JP",sans-serif}}
.hanmen{{width:390px;max-width:100%;margin:0 auto;background:var(--paper);overflow:hidden}}
.cover{{padding:20px 16px 32px;border-bottom:3px solid var(--spot)}}.logo,.genre{{font-size:10px;font-weight:900;letter-spacing:.2em}}
.vol{{font-size:72px;font-weight:900;line-height:1;color:var(--spot)}}h1{{font-size:42px;line-height:1.05;margin:8px 0}}
.lead-wrap{{display:flex;justify-content:flex-end;padding:24px 16px}}.lead-v{{writing-mode:vertical-rl;height:264px;line-height:2.15;font-size:13px}}
.item{{padding:24px 16px;border-top:1px solid}}h2{{font-size:28px;line-height:1.15;margin:6px 0 18px}}
.essay{{font-size:12px;line-height:2;text-align:justify;column-count:{design["columns"]};column-gap:14px;column-rule:1px solid}}
figure{{margin:0 0 18px}}img{{display:block;width:100%;height:auto}}figcaption{{font-size:9px;margin-top:4px}}
.data{{width:100%;border-collapse:collapse;font-size:10px;margin-top:18px}}.data th,.data td{{border:1px solid;padding:5px;text-align:left}}
.data th{{width:5em}}.data.reverse{{background:var(--ink);color:var(--paper)}}a{{color:inherit}}.folio{{display:flex;justify-content:space-between;font-size:9px;border-top:1px solid;margin-top:18px;padding-top:6px}}
.hanmen[data-layout="grid"] .cover{{display:grid;grid-template-columns:1fr 1fr;align-items:end}}.hanmen[data-layout="grid"] h1{{grid-column:1/3}}
.hanmen[data-layout="vertical"] h1{{writing-mode:vertical-rl;height:180px;margin-left:auto}}
.okuzuke{{font-size:9px;line-height:1.8;padding:24px 16px;border-top:4px double}}
</style>
</head>
<body><main class="hanmen" data-layout="{design["cover_layout"]}">
<header class="cover"><div class="logo">folio</div><div class="vol">VOL.{vol:03d}</div><h1>{e(title)}</h1><time>{e(str(issue["date"]))}</time></header>
<div class="lead-wrap"><p class="lead-v">{e(lead)}</p></div>
{''.join(sections)}
<footer class="okuzuke"><p>{OKUZUKE}</p>{powered}<p>folio / VOL.{vol:03d} / {e(str(issue["date"]))} / 発行元 folio</p><p>{colophon}</p></footer>
</main></body></html>
"""


def main(argv: list[str]) -> None:
    if len(argv) not in (3, 4):
        raise SystemExit("usage: render_issue.py 05.json design.json gera.html [07.json]")
    with open(argv[0], encoding="utf-8") as f:
        goudata = json.load(f)
    try:
        with open(argv[1], encoding="utf-8") as f:
            design = json.load(f)
    except FileNotFoundError:
        print(f"[warn] デザイン設定が未生成のため既定値で補完: {argv[1]}")
        design = {}
    except json.JSONDecodeError:
        print(f"[warn] デザイン設定が不正JSONのため既定値で補完: {argv[1]}")
        design = {}
    design = normalize_design(design, goudata["issue"].get("spot_color", "#1740C8"))
    with open(argv[1], "w", encoding="utf-8") as f:
        json.dump(design, f, ensure_ascii=False, indent=2)
    lead_final = None
    if len(argv) == 4:
        with open(argv[3], encoding="utf-8") as f:
            lead_final = json.load(f).get("lead_final")
    with open(argv[2], "w", encoding="utf-8") as f:
        f.write(render(goudata, design, lead_final))
    print(f"[ok] 決定論HTML生成: {argv[2]}")


if __name__ == "__main__":
    main(sys.argv[1:])
