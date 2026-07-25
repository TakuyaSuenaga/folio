import json

import pytest

import validate_chain


def sample():
    kikaku = {
        "vol": 9, "date": "2026-07-26", "title": "部分成功",
        "lead_draft": "リード", "genres": [
            {"genre": "book"}, {"genre": "music"},
        ],
    }
    candidate = {
        "cand_id": "book-01", "source_api": "openbd", "source_id": "isbn",
        "title": "本", "creator": "著者", "year": 2020,
        "links": [{"label": "見る", "url": "https://example.com", "kind": "reference"}],
        "verify": {"id_confirmed": True, "url_status": 200},
    }
    kouho = {
        "vol": 9,
        "genres": [{"genre": "book", "candidates": [candidate]}],
        "ng": [{"hacchu": "music", "reason": "候補なし"}],
    }
    item = {k: v for k, v in candidate.items()
            if k not in ("source_api", "source_id", "verify")}
    item.update({"genre": "book", "sentei_riyu": "理由", "essay": "本文"})
    genko = {
        "issue": {"vol": 9, "date": "2026-07-26", "title": "部分成功", "lead": "リード"},
        "items": [item],
    }
    return kikaku, kouho, genko


def test_partial_success_is_valid():
    assert validate_chain.validate(*sample()) == []


def test_all_genres_failed_empty_items_is_valid():
    kikaku, kouho, genko = sample()
    genko["items"] = []
    assert validate_chain.validate(kikaku, kouho, genko) == []


def test_unknown_candidate_fails():
    kikaku, kouho, genko = sample()
    genko["items"][0]["cand_id"] = "fabricated"
    assert any("02に存在しない" in e for e in validate_chain.validate(kikaku, kouho, genko))


def test_candidate_metadata_modification_fails():
    kikaku, kouho, genko = sample()
    genko["items"][0]["title"] = "改変"
    assert any(".title" in e for e in validate_chain.validate(kikaku, kouho, genko))


def test_dead_candidate_url_fails():
    kikaku, kouho, genko = sample()
    kouho["genres"][0]["candidates"][0]["verify"]["url_status"] = 404
    assert any("URL生存確認" in e for e in validate_chain.validate(kikaku, kouho, genko))


def test_main_outputs_has_items(tmp_path, capsys):
    values = sample()
    paths = []
    for index, value in enumerate(values):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        paths.append(str(path))
    validate_chain.main(paths)
    assert "has_items=true" in capsys.readouterr().out


def test_main_rejects_invalid_chain(tmp_path):
    values = sample()
    values[2]["items"][0]["cand_id"] = "fabricated"
    paths = []
    for index, value in enumerate(values):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        paths.append(str(path))
    with pytest.raises(SystemExit):
        validate_chain.main(paths)
