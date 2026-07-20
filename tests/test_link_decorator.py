import json

import link_decorator


def test_unknown_domain_is_not_sponsored_and_url_unchanged():
    # Arrange
    link = {"label": "版元ページ", "url": "https://example.com/x?a=1", "kind": "info"}

    # Act
    out = link_decorator.decorate(link)

    # Assert
    assert out["sponsored"] is False
    assert out["url"] == "https://example.com/x?a=1"
    assert "kind" not in out
    assert link["url"] == "https://example.com/x?a=1"  # 元オブジェクトを破壊しない


def test_rakuten_domain_is_sponsored_with_aff_param(monkeypatch):
    monkeypatch.setenv("RAKUTEN_AFF_PARAM", "scid=af_test123")
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/"}
    out = link_decorator.decorate(link)
    assert out["sponsored"] is True
    assert "scid=af_test123" in out["url"]


def test_rakuten_domain_without_aff_param_keeps_url(monkeypatch):
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/"}
    out = link_decorator.decorate(link)
    assert out["sponsored"] is True
    assert out["url"] == "https://books.rakuten.co.jp/rb/123/"


def test_main_writes_goudata(tmp_path, monkeypatch):
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    genko = {
        "issue": {"vol": 99, "date": "2026-07-19", "title": "テスト", "lead": "リード"},
        "items": [{"genre": "book", "cand_id": "b-01", "title": "t", "essay": "e",
                   "links": [{"label": "L", "url": "https://example.com/"}]}],
        "colophon": {"note": "VOL.099"},
    }
    src = tmp_path / "03_genko.json"
    dst = tmp_path / "05_goudata.json"
    src.write_text(json.dumps(genko, ensure_ascii=False), encoding="utf-8")

    link_decorator.main(str(src), str(dst))

    out = json.loads(dst.read_text(encoding="utf-8"))
    assert out["items"][0]["links"][0]["sponsored"] is False
    assert out["colophon"] == {"note": "VOL.099"}
    assert "decorated_at" in out
