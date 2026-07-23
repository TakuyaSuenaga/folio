#!/usr/bin/env python3
"""folio: Google Places テキスト検索(決定論)

usage: python scripts/places_search.py QUERY [QUERY ...]
結果を {query: {places: [...], error: null}} のJSONでstdoutに出す。
researcherがcafe/restaurant/architectureの候補を集めるために使う。

APIキーは環境変数 GOOGLE_PLACES_API_KEY からこのスクリプトが直接読む。
コマンドライン引数では**受け取らない** —— 呼び出し側のコマンドに `$GOOGLE_PLACES_API_KEY`
が現れると、CIのツール許可リスト(`Bash(python scripts/places_search.py *)`)が
シェル展開を含むコマンドを静的検証できず拒否するためである(vol.006のcafe全滅の原因)。
キーがモデルのコンテキストにもコマンドラインにも載らないという副次効果もある。
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_KEY_ENV = "GOOGLE_PLACES_API_KEY"
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PHOTO_MEDIA_URL_TEMPLATE = "https://places.googleapis.com/v1/{name}/media"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.googleMapsUri,places.primaryTypeDisplayName,places.photos"
)
LANGUAGE_CODE = "ja"
TIMEOUT_SEC = 10
DEFAULT_MAX_RESULTS = 10
PHOTO_MAX_WIDTH_PX = 1200
REDACTED = "***REDACTED***"


class PlacesError(Exception):
    """Places APIの障害。候補ゼロ(クエリが狭い)と区別するために送出する。"""


def _redact(text: str, secret: str) -> str:
    """例外メッセージがキー入りURLを丸ごと含むことがあるため、出力前に必ず通す。"""
    return text.replace(secret, REDACTED) if secret else text


def load_api_key() -> str:
    """環境変数からAPIキーを読む。未設定なら原因を明示して即座に落とす。"""
    key = os.environ.get(API_KEY_ENV, "")
    if not key:
        raise SystemExit(
            f"[error] 環境変数 {API_KEY_ENV} が未設定である。"
            "CIではワークフローの env: でSecretを渡すこと"
        )
    return key


def _post_json(url: str, body: dict, headers: dict, what: str, api_key: str) -> dict:
    """JSONをPOSTして返る。失敗はPlacesErrorに包む(キーは載せない)。"""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    return _read_json(req, what, api_key)


def _read_json(req: urllib.request.Request, what: str, api_key: str) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        raise PlacesError(_redact(f"{what}: HTTP {e.code} {e.reason}", api_key)) from None
    except Exception as e:
        raise PlacesError(_redact(f"{what}: {type(e).__name__}: {e}", api_key)) from None


def search_text(query: str, api_key: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """テキスト検索でplacesの生レスポンスを返す。0件は空リスト、障害はPlacesError。"""
    data = _post_json(
        SEARCH_URL,
        {"textQuery": query, "languageCode": LANGUAGE_CODE, "maxResultCount": max_results},
        {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        f"searchText({query})",
        api_key,
    )
    return data.get("places", [])


def resolve_photo(photo: dict, api_key: str) -> dict | None:
    """写真1枚をキー無しのphotoUriへ解決する。取れなければNone(沈黙省略)。

    mediaリクエストURLはキーを含むため、警告にもURLを出さない。
    """
    attributions = [
        {"name": a.get("displayName", ""), "uri": a.get("uri", "")}
        for a in photo.get("authorAttributions", [])
    ]
    if not attributions:
        return None   # 撮影者クレジットの無い写真はGoogleのポリシー上誌面に出せない

    name = photo.get("name", "")
    url = PHOTO_MEDIA_URL_TEMPLATE.format(name=name) + "?" + urllib.parse.urlencode(
        {"maxWidthPx": PHOTO_MAX_WIDTH_PX, "skipHttpRedirect": "true", "key": api_key}
    )
    try:
        data = _read_json(urllib.request.Request(url), f"photo({name})", api_key)
    except PlacesError as e:
        print(f"[warn] {e}", file=sys.stderr)
        return None

    photo_uri = data.get("photoUri", "")
    if not photo_uri:
        print(f"[warn] photo({name}): photoUriが空である", file=sys.stderr)
        return None
    return {"url": photo_uri, "source": "google-places", "attributions": attributions}


def build_place(raw: dict, api_key: str) -> dict:
    """レスポンスを候補の形へ転記する。補完・要約はしない。"""
    place = {
        "source_api": "google_places",
        "source_id": raw.get("id", ""),
        "title": raw.get("displayName", {}).get("text", ""),
        "address": raw.get("formattedAddress", ""),
        "google_maps_uri": raw.get("googleMapsUri", ""),
        "primary_type": raw.get("primaryTypeDisplayName", {}).get("text", ""),
    }
    photos = raw.get("photos", [])
    if not photos:
        return place
    image = resolve_photo(photos[0], api_key)
    if image is None:
        return place
    return {**place, "image": image}


def main(queries: list[str]) -> None:
    if not queries:
        raise SystemExit("usage: places_search.py QUERY [QUERY ...]")
    api_key = load_api_key()
    result = {}
    for query in queries:
        try:
            raws = search_text(query, api_key)
        except PlacesError as e:
            print(f"[warn] {e}", file=sys.stderr)
            result[query] = {"places": [], "error": str(e)}
            continue
        result[query] = {
            "places": [build_place(raw, api_key) for raw in raws],
            "error": None,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
