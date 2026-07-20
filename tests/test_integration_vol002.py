"""工程5→7前半→9 の決定論チェーンを vol.002 実データで通す統合テスト"""
import json
from pathlib import Path

import kousei_machine
import link_decorator
import publish

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vol-002"

DAICHO_V1 = """# folio 特集台帳

vol.001 | 2026-07-19 | 空港の時間 | music,film,architecture | 試し刷
"""


def test_full_deterministic_chain(tmp_path, monkeypatch):
    monkeypatch.delenv("RAKUTEN_AFF_PARAM", raising=False)
    monkeypatch.delenv("FOLIO_CHECK_URLS", raising=False)

    # 工程5: リンク加工 — 出力が既知の05と一致する
    goudata_path = tmp_path / "05_goudata.json"
    link_decorator.main(str(FIXTURES / "03_genko.json"), str(goudata_path))
    got = json.loads(goudata_path.read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "05_goudata.json").read_text(encoding="utf-8"))
    assert got["items"] == expected["items"]

    # 工程7前半: 機械校正 — 全項目pass
    machine_path = tmp_path / "machine.json"
    kousei_machine.main(str(goudata_path), str(FIXTURES / "vol-002.html"),
                        str(machine_path))
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    assert machine["genko_match"] is True
    assert machine["links_ok"] is True
    assert machine["html_ok"] is True

    # 工程9: 発行(vol.002の実judgmentは責了)
    root = tmp_path / "repo"
    (root / "editorial").mkdir(parents=True)
    (root / "editorial" / "daicho.md").write_text(DAICHO_V1, encoding="utf-8")
    desk = root / "desk" / "vol-002"
    desk.mkdir(parents=True)
    (desk / "07_kouryou.json").write_text(
        (FIXTURES / "07_kouryou.json").read_text(encoding="utf-8"), encoding="utf-8")
    (desk / "gera.html").write_text(
        (FIXTURES / "vol-002.html").read_text(encoding="utf-8"), encoding="utf-8")

    assert publish.publish(root, 2) == 0

    assert (root / "issues" / "vol-002.html").exists()
    index = (root / "issues" / "index.html").read_text(encoding="utf-8")
    assert "VOL.002" in index
    assert "氷" in index
    moushiokuri = (root / "editorial" / "moushiokuri.md").read_text(encoding="utf-8")
    assert "vol.002 校了時" in moushiokuri
