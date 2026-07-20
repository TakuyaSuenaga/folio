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
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TIMEOUT_SEC = 10
USER_AGENT = "Mozilla/5.0 (compatible; folio-linkcheck/1.0)"
HTTP_ERROR_THRESHOLD = 400
ALLOWED_SCHEMES = {"http", "https"}


def check_url(url: str) -> int | None:
    """HTTPステータスを実測する。到達不能・非http(s)スキームならNone。"""
    if urllib.parse.urlparse(url).scheme.lower() not in ALLOWED_SCHEMES:
        return None
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
