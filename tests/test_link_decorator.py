import json
from datetime import datetime

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


def test_parse_qsl_keeps_blank_query_values(monkeypatch):
    # Arrange: 空値クエリ(ref=)を含むURL
    monkeypatch.setenv("RAKUTEN_AFF_PARAM", "scid=af_test123")
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/?ref="}

    # Act
    out = link_decorator.decorate(link)

    # Assert: 空値パラメータが落とされず、AFFパラメータも付与される
    assert "ref=" in out["url"]
    assert "scid=af_test123" in out["url"]


def test_invalid_aff_param_without_equals_keeps_url_unchanged(monkeypatch, capsys):
    # Arrange: "=" を含まない不正形式のAFFパラメータ
    monkeypatch.setenv("RAKUTEN_AFF_PARAM", "noequalsign")
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/"}

    # Act
    out = link_decorator.decorate(link)

    # Assert: URLは無改変、sponsoredはTrueのまま、警告はstderrへ
    assert out["url"] == "https://books.rakuten.co.jp/rb/123/"
    assert out["sponsored"] is True
    err = capsys.readouterr().err
    assert "RAKUTEN_AFF_PARAM" in err


def test_invalid_aff_param_with_empty_key_keeps_url_unchanged(monkeypatch, capsys):
    # Arrange: keyが空("=value")の不正形式
    monkeypatch.setenv("RAKUTEN_AFF_PARAM", "=af_test123")
    link = {"label": "購入", "url": "https://books.rakuten.co.jp/rb/123/"}

    # Act
    out = link_decorator.decorate(link)

    # Assert
    assert out["url"] == "https://books.rakuten.co.jp/rb/123/"
    err = capsys.readouterr().err
    assert "RAKUTEN_AFF_PARAM" in err


def test_decorated_at_uses_jst_not_utc(tmp_path, monkeypatch):
    # Arrange: UTC 15:30(JST 0:30・日付繰り上がり境界)を模したdatetime
    class FakeDateTime:
        @classmethod
        def now(cls, tz):
            assert tz == link_decorator.JST
            return datetime(2026, 1, 2, 0, 30, tzinfo=tz)
    monkeypatch.setattr(link_decorator, "datetime", FakeDateTime)
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    genko = {
        "issue": {"vol": 1, "date": "2026-01-01", "title": "t", "lead": "l"},
        "items": [],
    }
    src = tmp_path / "03_genko.json"
    dst = tmp_path / "05_goudata.json"
    src.write_text(json.dumps(genko, ensure_ascii=False), encoding="utf-8")

    # Act
    link_decorator.main(str(src), str(dst))

    # Assert: JSTの日付(2026-01-02)が使われる
    out = json.loads(dst.read_text(encoding="utf-8"))
    assert out["decorated_at"] == "2026-01-02"
