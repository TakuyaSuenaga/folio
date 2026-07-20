import json
from pathlib import Path

import pytest

import publish

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vol-002"

DAICHO = """# folio 特集台帳

vol.001 | 2026-07-19 | 空港の時間 | music,film,architecture | 試し刷
"""


def make_repo(tmp_path, hantei="校了"):
    (tmp_path / "editorial").mkdir()
    (tmp_path / "editorial" / "daicho.md").write_text(DAICHO, encoding="utf-8")
    (tmp_path / "editorial" / "moushiokuri.md").write_text("# 申し送り\n", encoding="utf-8")
    desk = tmp_path / "desk" / "vol-002"
    desk.mkdir(parents=True)
    kouryou = json.loads((FIXTURES / "07_kouryou.json").read_text(encoding="utf-8"))
    kouryou["hantei"] = hantei
    (desk / "07_kouryou.json").write_text(
        json.dumps(kouryou, ensure_ascii=False), encoding="utf-8")
    (desk / "gera.html").write_text(
        (FIXTURES / "vol-002.html").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_parse_daicho():
    entries = publish.parse_daicho(DAICHO)
    assert entries == [{"vol": 1, "date": "2026-07-19", "title": "空港の時間",
                        "genres": "music,film,architecture", "summary": "試し刷"}]


def test_publish_kouryou_creates_issue_and_updates_records(tmp_path):
    root = make_repo(tmp_path)

    assert publish.publish(root, 2) == 0

    assert (root / "issues" / "vol-002.html").exists()
    daicho = (root / "editorial" / "daicho.md").read_text(encoding="utf-8")
    assert "vol.002 | 2026-07-19 | 氷" in daicho
    index = (root / "issues" / "index.html").read_text(encoding="utf-8")
    assert "氷" in index
    assert 'href="./vol-002.html"' in index
    moushiokuri = (root / "editorial" / "moushiokuri.md").read_text(encoding="utf-8")
    assert "## 2026-07-19 (vol.002 校了時)" in moushiokuri


def test_publish_kyukan_returns_2_and_writes_nothing(tmp_path):
    root = make_repo(tmp_path, hantei="休刊")

    assert publish.publish(root, 2) == publish.EXIT_KYUKAN

    assert not (root / "issues" / "vol-002.html").exists()
    assert "vol.002" not in (root / "editorial" / "daicho.md").read_text(encoding="utf-8")


def test_publish_missing_keys_exits(tmp_path):
    root = make_repo(tmp_path)
    (root / "desk" / "vol-002" / "07_kouryou.json").write_text(
        json.dumps({"vol": 2, "hantei": "校了"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        publish.publish(root, 2)


def test_publish_unknown_hantei_exits(tmp_path):
    root = make_repo(tmp_path, hantei="なんとなく")
    with pytest.raises(SystemExit):
        publish.publish(root, 2)


def test_publish_malformed_daicho_line_exits_and_writes_nothing(tmp_path):
    # Arrange: DAICHO_LINE_REにマッチしない不正形式のdaicho_line
    root = make_repo(tmp_path)
    kouryou_path = root / "desk" / "vol-002" / "07_kouryou.json"
    kouryou = json.loads(kouryou_path.read_text(encoding="utf-8"))
    kouryou["daicho_line"] = "これは台帳行の形式ではない"
    kouryou_path.write_text(json.dumps(kouryou, ensure_ascii=False), encoding="utf-8")

    # Act & Assert
    with pytest.raises(SystemExit):
        publish.publish(root, 2)

    # Assert: 号ページも台帳も書き換わらない
    assert not (root / "issues" / "vol-002.html").exists()
    assert "vol.002" not in (root / "editorial" / "daicho.md").read_text(encoding="utf-8")


def test_publish_daicho_line_vol_mismatch_exits_and_writes_nothing(tmp_path):
    # Arrange: daicho_line内のvol番号(003)が引数vol(2)と食い違う
    root = make_repo(tmp_path)
    kouryou_path = root / "desk" / "vol-002" / "07_kouryou.json"
    kouryou = json.loads(kouryou_path.read_text(encoding="utf-8"))
    kouryou["daicho_line"] = kouryou["daicho_line"].replace("vol.002", "vol.003")
    kouryou_path.write_text(json.dumps(kouryou, ensure_ascii=False), encoding="utf-8")

    # Act & Assert
    with pytest.raises(SystemExit):
        publish.publish(root, 2)

    assert not (root / "issues" / "vol-002.html").exists()
    assert "vol.002" not in (root / "editorial" / "daicho.md").read_text(encoding="utf-8")


def test_publish_kouryou_vol_field_mismatch_exits_and_writes_nothing(tmp_path):
    # Arrange: 07_kouryou.json自体のvolフィールドが引数volと食い違う
    root = make_repo(tmp_path)
    kouryou_path = root / "desk" / "vol-002" / "07_kouryou.json"
    kouryou = json.loads(kouryou_path.read_text(encoding="utf-8"))
    kouryou["vol"] = 3
    kouryou_path.write_text(json.dumps(kouryou, ensure_ascii=False), encoding="utf-8")

    # Act & Assert
    with pytest.raises(SystemExit):
        publish.publish(root, 2)

    assert not (root / "issues" / "vol-002.html").exists()
    assert "vol.002" not in (root / "editorial" / "daicho.md").read_text(encoding="utf-8")


def test_update_moushiokuri_appends_and_trims():
    text = "# 申し送り\n"
    for i in range(20):
        text = publish.update_moushiokuri(
            text, f"2026-07-{i + 1:02d}", i + 1, f"メモ{i + 1:02d}")
    assert text.count("## ") == publish.MOUSHIOKURI_KEEP
    assert "メモ20" in text
    assert "メモ07" in text   # 20 - 14 + 1 = 7 番目から残る
    assert "メモ06" not in text


def test_update_moushiokuri_splits_nakaguro_bullets():
    out = publish.update_moushiokuri("# 申し送り\n", "2026-07-19", 2, "・一つ目 ・二つ目")
    assert "- 一つ目" in out
    assert "- 二つ目" in out


def test_update_moushiokuri_keeps_proper_noun_nakaguro_intact():
    # Arrange: 固有名詞中の中黒(空白を伴わない)は分割対象ではない
    message = "アンナ・カヴァンの新刊情報 ・氷菓子の記事も追加"

    # Act
    out = publish.update_moushiokuri("# 申し送り\n", "2026-07-19", 2, message)

    # Assert: 「アンナ・カヴァン」は分断されず、箇条書き区切りだけ分割される
    assert "- アンナ・カヴァンの新刊情報" in out
    assert "- 氷菓子の記事も追加" in out


def test_render_index_escapes_html():
    entries = [{"vol": 1, "date": "2026-07-19", "title": "<氷>",
                "genres": "book", "summary": "a&b"}]
    html = publish.render_index(entries)
    assert "&lt;氷&gt;" in html
    assert "a&amp;b" in html
    assert "<script" not in html
