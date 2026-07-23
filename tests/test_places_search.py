import io
import json
import urllib.error

import pytest

import places_search

API_KEY = "test-secret-key-abc123"


class FakeResponse:
    def __init__(self, payload, status=200):
        self._body = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_urlopen(payload_by_url, recorder=None):
    """URLの部分一致でレスポンスを返すfake urlopen。requestはrecorderに積む。"""
    def fake_urlopen(req, timeout=None):
        if recorder is not None:
            recorder.append(req)
        for fragment, payload in payload_by_url.items():
            if fragment in req.full_url:
                return FakeResponse(payload)
        raise AssertionError(f"未登録のURLが叩かれた: {req.full_url}")
    return fake_urlopen


SEARCH_PAYLOAD = {
    "places": [
        {
            "id": "ChIJ_place_001",
            "displayName": {"text": "喫茶ソワレ", "languageCode": "ja"},
            "formattedAddress": "京都府京都市下京区",
            "googleMapsUri": "https://maps.google.com/?cid=1",
            "photos": [
                {
                    "name": "places/ChIJ_place_001/photos/PHOTO_REF",
                    "authorAttributions": [
                        {"displayName": "山田太郎", "uri": "https://maps.google.com/contrib/1"}
                    ],
                }
            ],
        }
    ]
}

PHOTO_PAYLOAD = {"photoUri": "https://lh3.googleusercontent.com/places/keyless-photo"}


# --- APIキーの取り扱い(境界での検証) ---

def test_load_api_key_returns_value_from_env(monkeypatch):
    # Arrange
    monkeypatch.setenv(places_search.API_KEY_ENV, API_KEY)

    # Act / Assert
    assert places_search.load_api_key() == API_KEY


def test_load_api_key_exits_when_env_is_unset(monkeypatch):
    # Arrange
    monkeypatch.delenv(places_search.API_KEY_ENV, raising=False)

    # Act / Assert: 原因不明の0件ではなく明示的な失敗にする
    with pytest.raises(SystemExit) as e:
        places_search.load_api_key()
    assert places_search.API_KEY_ENV in str(e.value)


def test_load_api_key_exits_when_env_is_empty(monkeypatch):
    # Arrange
    monkeypatch.setenv(places_search.API_KEY_ENV, "")

    # Act / Assert
    with pytest.raises(SystemExit):
        places_search.load_api_key()


# --- 検索 ---

def test_search_text_sends_key_in_header_not_in_url(monkeypatch):
    # Arrange: キーはヘッダで渡す。URLに載るとログや保存物へ漏れる
    reqs = []
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": SEARCH_PAYLOAD}, reqs))

    # Act
    places_search.search_text("喫茶店 京都", API_KEY)

    # Assert
    req = reqs[0]
    assert req.get_header("X-goog-api-key") == API_KEY
    assert API_KEY not in req.full_url


def test_search_text_requests_photos_in_field_mask(monkeypatch):
    # Arrange: field maskにphotosが無いとattributionsが返らず誌面に写真を出せない
    reqs = []
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": SEARCH_PAYLOAD}, reqs))

    # Act
    places_search.search_text("喫茶店 京都", API_KEY)

    # Assert
    assert "places.photos" in reqs[0].get_header("X-goog-fieldmask")


def test_search_text_sends_query_as_japanese_text_query(monkeypatch):
    # Arrange
    reqs = []
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": SEARCH_PAYLOAD}, reqs))

    # Act
    places_search.search_text("喫茶店 京都", API_KEY)

    # Assert
    body = json.loads(reqs[0].data.decode())
    assert body["textQuery"] == "喫茶店 京都"
    assert body["languageCode"] == "ja"


def test_search_text_returns_places_from_response(monkeypatch):
    # Arrange
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": SEARCH_PAYLOAD}))

    # Act
    places = places_search.search_text("喫茶店 京都", API_KEY)

    # Assert
    assert [p["id"] for p in places] == ["ChIJ_place_001"]


def test_search_text_returns_empty_list_when_response_has_no_places(monkeypatch):
    # Arrange: 0件はAPI障害ではない(クエリが狭いだけ)
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": {}}))

    # Act / Assert
    assert places_search.search_text("存在しない語", API_KEY) == []


def test_search_text_raises_places_error_on_http_error(monkeypatch):
    # Arrange
    def raise_403(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO())
    monkeypatch.setattr(places_search.urllib.request, "urlopen", raise_403)

    # Act / Assert: 0件と障害を呼び出し側が区別できるよう例外で分ける
    with pytest.raises(places_search.PlacesError) as e:
        places_search.search_text("喫茶店 京都", API_KEY)
    assert "403" in str(e.value)


def test_search_text_error_message_does_not_leak_key(monkeypatch):
    # Arrange
    def raise_400(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO())
    monkeypatch.setattr(places_search.urllib.request, "urlopen", raise_400)

    # Act / Assert
    with pytest.raises(places_search.PlacesError) as e:
        places_search.search_text("喫茶店 京都", API_KEY)
    assert API_KEY not in str(e.value)


# --- 写真 ---

def test_resolve_photo_returns_keyless_uri_with_attributions(monkeypatch):
    # Arrange
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"/media": PHOTO_PAYLOAD}))

    # Act
    image = places_search.resolve_photo(SEARCH_PAYLOAD["places"][0]["photos"][0], API_KEY)

    # Assert
    assert image["url"] == PHOTO_PAYLOAD["photoUri"]
    assert image["source"] == "google-places"
    assert image["attributions"] == [
        {"name": "山田太郎", "uri": "https://maps.google.com/contrib/1"}
    ]
    assert "key=" not in image["url"]


def test_resolve_photo_returns_none_without_attributions(monkeypatch):
    # Arrange: 撮影者クレジットの無い写真は権利上誌面に出せない
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"/media": PHOTO_PAYLOAD}))
    photo = {"name": "places/X/photos/Y", "authorAttributions": []}

    # Act / Assert
    assert places_search.resolve_photo(photo, API_KEY) is None


def test_resolve_photo_returns_none_on_http_error(monkeypatch, capsys):
    # Arrange
    def raise_404(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "NF", {}, io.BytesIO())
    monkeypatch.setattr(places_search.urllib.request, "urlopen", raise_404)

    # Act: 写真の欠落は号を落とす理由にならないので沈黙省略する(理由はstderrに残す)
    image = places_search.resolve_photo(SEARCH_PAYLOAD["places"][0]["photos"][0], API_KEY)

    # Assert
    assert image is None
    assert "404" in capsys.readouterr().err


def test_resolve_photo_warning_does_not_leak_key(monkeypatch, capsys):
    # Arrange: mediaリクエストURLはキーを含むため、警告にURLをそのまま出さない
    def raise_500(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "ISE", {}, io.BytesIO())
    monkeypatch.setattr(places_search.urllib.request, "urlopen", raise_500)

    # Act
    places_search.resolve_photo(SEARCH_PAYLOAD["places"][0]["photos"][0], API_KEY)

    # Assert
    assert API_KEY not in capsys.readouterr().err


def test_resolve_photo_redacts_key_embedded_in_exception_message(monkeypatch, capsys):
    # Arrange: 例外メッセージがmediaリクエストURL(キー入り)を丸ごと含む場合がある
    def raise_with_url(req, timeout=None):
        raise ValueError(f"unknown url type: {req.full_url}")
    monkeypatch.setattr(places_search.urllib.request, "urlopen", raise_with_url)

    # Act
    image = places_search.resolve_photo(SEARCH_PAYLOAD["places"][0]["photos"][0], API_KEY)

    # Assert
    err = capsys.readouterr().err
    assert image is None
    assert API_KEY not in err
    assert "REDACTED" in err


# --- 候補の組み立て ---

def test_build_place_transcribes_response_fields(monkeypatch):
    # Arrange
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"/media": PHOTO_PAYLOAD}))

    # Act
    place = places_search.build_place(SEARCH_PAYLOAD["places"][0], API_KEY)

    # Assert
    assert place["source_api"] == "google_places"
    assert place["source_id"] == "ChIJ_place_001"
    assert place["title"] == "喫茶ソワレ"
    assert place["address"] == "京都府京都市下京区"
    assert place["google_maps_uri"] == "https://maps.google.com/?cid=1"


def test_build_place_omits_image_when_place_has_no_photo(monkeypatch):
    # Arrange: 写真の無い場所はimageを付けない(openBDの空coverと同じ沈黙省略)
    def fail_if_called(req, timeout=None):
        raise AssertionError("写真が無いときにmediaを叩いてはいけない")
    monkeypatch.setattr(places_search.urllib.request, "urlopen", fail_if_called)
    raw = {"id": "X", "displayName": {"text": "写真無し"}, "formattedAddress": "東京都"}

    # Act
    place = places_search.build_place(raw, API_KEY)

    # Assert
    assert "image" not in place


def test_resolve_photo_returns_none_when_photo_uri_is_empty(monkeypatch, capsys):
    # Arrange: 200で返ってもphotoUriが空なら誌面に出せない
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"/media": {"photoUri": ""}}))

    # Act
    image = places_search.resolve_photo(SEARCH_PAYLOAD["places"][0]["photos"][0], API_KEY)

    # Assert
    assert image is None
    assert "photoUri" in capsys.readouterr().err


def test_build_place_omits_image_when_photo_cannot_be_resolved(monkeypatch):
    # Arrange: 写真はあるがクレジットが無く採用できないケース
    monkeypatch.setattr(places_search, "resolve_photo", lambda photo, key: None)

    # Act
    place = places_search.build_place(SEARCH_PAYLOAD["places"][0], API_KEY)

    # Assert
    assert "image" not in place
    assert place["source_id"] == "ChIJ_place_001"


def test_build_place_uses_only_first_photo(monkeypatch):
    # Arrange: 採用するのは1枚だけ
    reqs = []
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"/media": PHOTO_PAYLOAD}, reqs))
    raw = dict(SEARCH_PAYLOAD["places"][0])
    raw["photos"] = raw["photos"] + [
        {"name": "places/X/photos/SECOND", "authorAttributions": [{"displayName": "B", "uri": "u"}]}
    ]

    # Act
    places_search.build_place(raw, API_KEY)

    # Assert
    assert len(reqs) == 1
    assert "PHOTO_REF" in reqs[0].full_url


# --- CLI ---

def test_main_outputs_places_per_query(monkeypatch, capsys):
    # Arrange
    monkeypatch.setenv(places_search.API_KEY_ENV, API_KEY)
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": SEARCH_PAYLOAD, "/media": PHOTO_PAYLOAD}))

    # Act
    places_search.main(["喫茶店 京都"])

    # Assert
    out = json.loads(capsys.readouterr().out)
    assert out["喫茶店 京都"]["error"] is None
    assert out["喫茶店 京都"]["places"][0]["source_id"] == "ChIJ_place_001"


def test_main_records_error_per_query_instead_of_aborting(monkeypatch, capsys):
    # Arrange: 障害を0件と誤認させない(vol.006でcafeが原因不明のゼロ件になった再発防止)
    monkeypatch.setenv(places_search.API_KEY_ENV, API_KEY)

    def raise_429(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO())
    monkeypatch.setattr(places_search.urllib.request, "urlopen", raise_429)

    # Act
    places_search.main(["喫茶店 京都"])

    # Assert
    out = json.loads(capsys.readouterr().out)
    assert out["喫茶店 京都"]["places"] == []
    assert "429" in out["喫茶店 京都"]["error"]


def test_main_output_never_contains_api_key(monkeypatch, capsys):
    # Arrange: 出力はdesk/へ保存されるためキーが一文字も混ざってはいけない
    monkeypatch.setenv(places_search.API_KEY_ENV, API_KEY)
    monkeypatch.setattr(places_search.urllib.request, "urlopen",
                        make_urlopen({"places:searchText": SEARCH_PAYLOAD, "/media": PHOTO_PAYLOAD}))

    # Act
    places_search.main(["喫茶店 京都"])

    # Assert
    captured = capsys.readouterr()
    assert API_KEY not in captured.out
    assert API_KEY not in captured.err


def test_main_without_queries_exits(monkeypatch):
    # Arrange
    monkeypatch.setenv(places_search.API_KEY_ENV, API_KEY)

    # Act / Assert
    with pytest.raises(SystemExit):
        places_search.main([])
