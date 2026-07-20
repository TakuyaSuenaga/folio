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
