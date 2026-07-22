import io
import json
import urllib.error

import pytest

import verify_links


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_check_url_returns_status(monkeypatch):
    monkeypatch.setattr(verify_links.urllib.request, "urlopen",
                        lambda req, timeout: FakeResponse(200))
    assert verify_links.check_url("https://example.com/") == 200


def test_check_url_returns_http_error_code(monkeypatch):
    def raise_404(req, timeout):
        raise urllib.error.HTTPError("https://example.com/", 404, "NF", {}, io.BytesIO())
    monkeypatch.setattr(verify_links.urllib.request, "urlopen", raise_404)
    assert verify_links.check_url("https://example.com/") == 404


def test_check_url_returns_none_when_unreachable(monkeypatch):
    def raise_err(req, timeout):
        raise urllib.error.URLError("dns failure")
    monkeypatch.setattr(verify_links.urllib.request, "urlopen", raise_err)
    assert verify_links.check_url("https://nx.invalid/") is None


def test_main_outputs_json(monkeypatch, capsys):
    monkeypatch.setattr(verify_links, "check_url",
                        lambda u: 200 if "ok" in u else None)
    verify_links.main(["https://ok.example/", "https://ng.example/"])
    out = json.loads(capsys.readouterr().out)
    assert out["https://ok.example/"]["ok"] is True
    assert out["https://ng.example/"]["ok"] is False
    assert out["https://ng.example/"]["url_status"] is None
    assert "checked_at" in out["https://ok.example/"]


def test_main_without_urls_exits():
    with pytest.raises(SystemExit):
        verify_links.main([])


def test_check_url_logs_failure_reason_to_stderr(monkeypatch, capsys):
    # Arrange: 到達不能の失敗理由がstderrに一行残る(silent swallowしない)
    def raise_err(req, timeout):
        raise urllib.error.URLError("dns failure")
    monkeypatch.setattr(verify_links.urllib.request, "urlopen", raise_err)

    # Act
    result = verify_links.check_url("https://nx.invalid/")

    # Assert
    assert result is None
    err = capsys.readouterr().err
    assert "https://nx.invalid/" in err
    assert "dns failure" in err


def test_check_url_returns_none_for_non_http_scheme(monkeypatch):
    # Arrange: file:// 等の非http(s)スキームはurlopenを呼ばずNoneを返す
    def fail_if_called(req, timeout):
        raise AssertionError("非http(s)スキームでurlopenが呼ばれてはいけない")
    monkeypatch.setattr(verify_links.urllib.request, "urlopen", fail_if_called)

    # Act
    result = verify_links.check_url("file:///etc/passwd")

    # Assert
    assert result is None
