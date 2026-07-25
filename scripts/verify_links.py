#!/usr/bin/env python3
"""folio: URL死活確認(決定論)

usage: python scripts/verify_links.py URL [URL...]
結果を {url: {url_status, ok, checked_at}} のJSONでstdoutに出す。
researcherが02_kouho.jsonのverify欄を埋めるために使う。
kousei_machine.pyもCIでのリンク死活実測に使う。
"""
import json
import ipaddress
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TIMEOUT_SEC = 10
USER_AGENT = "Mozilla/5.0 (compatible; folio-linkcheck/1.0)"
HTTP_ERROR_THRESHOLD = 400
ALLOWED_SCHEMES = {"http", "https"}


def _is_public_host(host: str) -> bool:
    """接続前に、解決された全アドレスがグローバルな場合だけ許可する。"""
    if not host or host.lower() == "localhost":
        return False
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(addr).is_global for addr in addresses)


class PublicOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlparse(newurl)
        if parts.scheme.lower() not in ALLOWED_SCHEMES or not _is_public_host(parts.hostname or ""):
            raise urllib.error.URLError("公開ネットワーク外へのリダイレクトを拒否")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(PublicOnlyRedirectHandler)


def _open(req: urllib.request.Request):
    return _OPENER.open(req, timeout=TIMEOUT_SEC)


def check_url(url: str) -> int | None:
    """HTTPステータスを実測する。到達不能・非http(s)スキームならNone。"""
    parts = urllib.parse.urlparse(url)
    if (parts.scheme.lower() not in ALLOWED_SCHEMES
            or not _is_public_host(parts.hostname or "")):
        print(f"[warn] 公開HTTP(S) URLではないため拒否: {url}", file=sys.stderr)
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _open(req) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        print(f"[warn] {url}: {type(e).__name__}: {e}", file=sys.stderr)
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
