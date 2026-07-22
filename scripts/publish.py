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
# LLMが書く07_kouryou.jsonは型が揺れうるため、書き込み開始前にキーの存在と型の両方を検証する
REQUIRED_KEYS = (("vol", int), ("hantei", str), ("daicho_line", str), ("moushiokuri", str))
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
    entries = sorted(entries, key=lambda x: x["vol"])  # 台帳の行順が崩れていても最新号=vol最大
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
    raw_parts = re.split(r"\n+|[ 　]+・", message)
    parts = []
    for p in raw_parts:
        p = p.strip().lstrip("・").strip()
        if p:
            parts.append(p)
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
    missing = [k for k, _ in REQUIRED_KEYS if k not in kouryou]
    if missing:
        raise SystemExit(f"[error] 07_kouryou.json に必須キーが無い: {missing}")
    wrong_type = [k for k, t in REQUIRED_KEYS if not isinstance(kouryou[k], t)]
    if wrong_type:
        raise SystemExit(f"[error] 07_kouryou.json のキーの型が不正: {wrong_type}")

    if kouryou["vol"] != vol:
        raise SystemExit(
            f"[error] 07_kouryou.json の vol({kouryou['vol']}) が引数vol({vol})と不一致")

    hantei = kouryou["hantei"]
    if hantei == "休刊":
        print(f"[kyukan] vol.{vol:03d}: {kouryou.get('riyu', '(理由未記載)')}",
              file=sys.stderr)
        return EXIT_KYUKAN
    if hantei not in ("校了", "責了"):
        raise SystemExit(f"[error] 不明なhantei: {hantei}")

    daicho_line = kouryou["daicho_line"].strip()
    daicho_match = DAICHO_LINE_RE.match(daicho_line)
    if not daicho_match:
        raise SystemExit(f"[error] daicho_line の形式が不正: {daicho_line!r}")
    if int(daicho_match.group(1)) != vol:
        raise SystemExit(
            f"[error] daicho_line のvol({daicho_match.group(1)}) が引数vol({vol})と不一致")

    gera = desk / "gera.html"
    if not gera.exists():
        raise SystemExit(f"[error] {gera} が無い")

    # ここまでで検証を終え、新しい内容を全て生成してから書き込む。
    # 途中で失敗しても中途半端な状態(号ページだけ公開・台帳だけ追記)を残さないため
    daicho_path = root / "editorial" / "daicho.md"
    text = daicho_path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    text += daicho_line + "\n"

    m = DATE_RE.search(daicho_line)
    date_str = m.group(1) if m else datetime.now(JST).date().isoformat()
    moushiokuri_path = root / "editorial" / "moushiokuri.md"
    existing = (moushiokuri_path.read_text(encoding="utf-8")
                if moushiokuri_path.exists() else "# 申し送り\n")
    new_moushiokuri = update_moushiokuri(
        existing, date_str, vol, kouryou["moushiokuri"])
    index_html = render_index(parse_daicho(text))

    issues = root / "issues"
    issues.mkdir(exist_ok=True)
    shutil.copyfile(gera, issues / f"vol-{vol:03d}.html")
    daicho_path.write_text(text, encoding="utf-8")
    moushiokuri_path.write_text(new_moushiokuri, encoding="utf-8")
    (issues / "index.html").write_text(index_html, encoding="utf-8")
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
    try:
        vol = int(argv[0])
    except ValueError:
        raise SystemExit(f"[error] volは数値で指定する: {argv[0]!r}")
    sys.exit(publish(root, vol))


if __name__ == "__main__":
    main(sys.argv[1:])
