import io
import json
import urllib.error
import urllib.request

import pytest

import api_fetch


class FakeResponse:
    def __init__(self, body: bytes, status=200):
        self._body = body
        self.status = status

    def read(self, amt=None):
        return self._body if amt is None else self._body[:amt]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def json_response(payload, status=200):
    return FakeResponse(json.dumps(payload).encode(), status)


# --- 許可判定 -------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://ndlsearch.ndl.go.jp/api/opensearch?any=%E9%9B%B2&cnt=20",
    "https://api.openbd.jp/v1/get?isbn=9784750359731",
    "https://itunes.apple.com/search?term=jazz&country=JP&media=music",
])
def test_is_allowed_url_accepts_research_apis(url):
    assert api_fetch.is_allowed_url(url) is True


def test_is_allowed_url_rejects_unknown_host():
    assert api_fetch.is_allowed_url("https://attacker.example/collect") is False


def test_is_allowed_url_rejects_plain_http():
    # Arrange: 許可ホストでもhttpは平文なので通さない
    assert api_fetch.is_allowed_url("http://api.openbd.jp/v1/get?isbn=1") is False


def test_is_allowed_url_rejects_suffix_lookalike_host():
    # Arrange: 前方一致ではなく完全一致であること
    assert api_fetch.is_allowed_url("https://itunes.apple.com.attacker.example/") is False


def test_is_allowed_url_rejects_userinfo_disguise():
    # Arrange: userinfoに許可ホストを書いて実ホストを偽装する古典的な手
    assert api_fetch.is_allowed_url("https://itunes.apple.com@attacker.example/") is False


def test_is_allowed_url_rejects_non_http_scheme():
    assert api_fetch.is_allowed_url("file:///etc/passwd") is False


# --- 取得 -----------------------------------------------------------------

def test_fetch_parses_json_body(monkeypatch):
    # Arrange
    monkeypatch.setattr(api_fetch, "_open", lambda req: json_response({"resultCount": 1}))

    # Act
    result = api_fetch.fetch("https://itunes.apple.com/search?term=jazz")

    # Assert
    assert result["ok"] is True
    assert result["status"] == 200
    assert result["body"] == {"resultCount": 1}
    assert result["error"] is None


def test_fetch_returns_text_body_for_xml(monkeypatch):
    # Arrange: NDLサーチのopensearchはRSS(XML)を返す
    xml = b"<?xml version='1.0'?><rss><channel><item/></channel></rss>"
    monkeypatch.setattr(api_fetch, "_open", lambda req: FakeResponse(xml))

    # Act
    result = api_fetch.fetch("https://ndlsearch.ndl.go.jp/api/opensearch?any=x")

    # Assert
    assert result["ok"] is True
    assert result["body"] == xml.decode()


def test_fetch_blocks_disallowed_host_without_opening_socket(monkeypatch):
    # Arrange
    def fail_if_called(req):
        raise AssertionError("許可ホスト外でHTTPを開いてはいけない")
    monkeypatch.setattr(api_fetch, "_open", fail_if_called)

    # Act
    result = api_fetch.fetch("https://attacker.example/collect?d=leak")

    # Assert
    assert result["ok"] is False
    assert result["status"] is None
    assert result["body"] is None
    assert "許可" in result["error"]


def test_fetch_records_http_error(monkeypatch):
    # Arrange
    def raise_404(req):
        raise urllib.error.HTTPError(
            "https://api.openbd.jp/v1/get", 404, "Not Found", {}, io.BytesIO())
    monkeypatch.setattr(api_fetch, "_open", raise_404)

    # Act
    result = api_fetch.fetch("https://api.openbd.jp/v1/get?isbn=1")

    # Assert
    assert result["ok"] is False
    assert result["status"] == 404
    assert "404" in result["error"]


def test_fetch_records_unreachable_host(monkeypatch, capsys):
    # Arrange
    def raise_err(req):
        raise urllib.error.URLError("dns failure")
    monkeypatch.setattr(api_fetch, "_open", raise_err)

    # Act
    result = api_fetch.fetch("https://api.openbd.jp/v1/get?isbn=1")

    # Assert: 理由を握り潰さずstderrにも残す
    assert result["ok"] is False
    assert result["status"] is None
    assert "dns failure" in result["error"]
    assert "dns failure" in capsys.readouterr().err


def test_fetch_truncates_oversized_body(monkeypatch):
    # Arrange: 上限を超えるレスポンスでモデルのコンテキストを溢れさせない
    huge = b"a" * (api_fetch.MAX_BODY_BYTES + 100)
    monkeypatch.setattr(api_fetch, "_open", lambda req: FakeResponse(huge))

    # Act
    result = api_fetch.fetch("https://ndlsearch.ndl.go.jp/api/opensearch?any=x")

    # Assert
    assert result["ok"] is True
    assert result["body"].endswith(api_fetch.TRUNCATION_MARK)
    assert len(result["body"]) == api_fetch.MAX_BODY_BYTES + len(api_fetch.TRUNCATION_MARK)


# --- リダイレクト ---------------------------------------------------------

def test_redirect_to_disallowed_host_is_blocked():
    # Arrange: 許可ホストが外部へ302を返す経路を塞ぐ
    handler = api_fetch.AllowlistRedirectHandler()
    req = urllib.request.Request("https://api.openbd.jp/v1/get?isbn=1")

    # Act / Assert
    with pytest.raises(api_fetch.BlockedURLError):
        handler.redirect_request(
            req, io.BytesIO(), 302, "Found", {}, "https://attacker.example/collect")


def test_redirect_within_allowlist_is_permitted():
    # Arrange
    handler = api_fetch.AllowlistRedirectHandler()
    req = urllib.request.Request("https://api.openbd.jp/v1/get?isbn=1")

    # Act
    redirected = handler.redirect_request(
        req, io.BytesIO(), 302, "Found", {}, "https://api.openbd.jp/v1/get?isbn=2")

    # Assert
    assert redirected is not None
    assert redirected.full_url == "https://api.openbd.jp/v1/get?isbn=2"


# --- CLI ------------------------------------------------------------------

def test_main_outputs_json_keyed_by_url(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(api_fetch, "fetch",
                        lambda u: {"status": 200, "ok": True, "body": {"u": u}, "error": None})

    # Act
    api_fetch.main(["https://api.openbd.jp/v1/get?isbn=1", "https://itunes.apple.com/search"])

    # Assert
    out = json.loads(capsys.readouterr().out)
    assert list(out) == [
        "https://api.openbd.jp/v1/get?isbn=1", "https://itunes.apple.com/search"]
    assert out["https://itunes.apple.com/search"]["ok"] is True


def test_main_without_urls_exits():
    with pytest.raises(SystemExit):
        api_fetch.main([])
