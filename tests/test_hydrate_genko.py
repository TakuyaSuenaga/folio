import hydrate_genko


def data():
    kikaku = {
        "vol": 9, "date": "2026-07-26", "title": "更新",
        "lead_draft": "リード", "spot_color": "#123456",
    }
    candidate = {
        "cand_id": "rest-01", "source_api": "google_places", "source_id": "p1",
        "title": "店", "creator": "", "meta": {"address": "東京"},
        "links": [{"label": "地図", "url": "https://example.com", "kind": "map"}],
        "verify": {"id_confirmed": True, "url_status": 200},
    }
    kouho = {"genres": [{"genre": "restaurant", "candidates": [candidate]}]}
    draft = {
        "items": [{"cand_id": "rest-01", "sentei_riyu": "理由", "essay": "本文",
                   "year": 1900, "title": "改変", "links": []}],
    }
    return kikaku, kouho, draft


def test_hydrate_rebuilds_all_candidate_fields_and_normalizes_missing():
    result, dropped = hydrate_genko.hydrate(*data())
    item = result["items"][0]
    assert dropped == []
    assert item["title"] == "店"
    assert item["year"] is None
    assert item["publisher"] == ""
    assert item["links"][0]["kind"] == "map"
    assert result["issue"]["lead"] == "リード"


def test_hydrate_drops_only_invalid_item():
    kikaku, kouho, draft = data()
    draft["items"].insert(0, {"cand_id": "fake", "essay": "本文", "sentei_riyu": "理由"})
    result, dropped = hydrate_genko.hydrate(kikaku, kouho, draft)
    assert [item["cand_id"] for item in result["items"]] == ["rest-01"]
    assert dropped[0]["cand_id"] == "fake"


def test_hydrate_all_invalid_becomes_empty_for_kyukan():
    kikaku, kouho, draft = data()
    draft["items"] = [{"cand_id": "fake", "essay": "本文", "sentei_riyu": "理由"}]
    result, dropped = hydrate_genko.hydrate(kikaku, kouho, draft)
    assert result["items"] == []
    assert len(dropped) == 1
