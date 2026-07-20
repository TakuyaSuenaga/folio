from datetime import date

import pytest

import seed

DAICHO = """# folio 特集台帳

vol.001 | 2026-07-19 | 空港の時間 | music,film,architecture | 試し刷
vol.002 | 2026-07-19 | 氷 | book,cafe | 迫る氷と消える氷
"""


def test_next_vol_increments_last():
    assert seed.next_vol(DAICHO) == 3


def test_next_vol_defaults_to_1():
    assert seed.next_vol("# 台帳\n") == 1


@pytest.mark.parametrize("d,name", [
    (date(2026, 7, 19), "小暑"),
    (date(2026, 7, 22), "大暑"),
    (date(2026, 1, 2), "冬至"),
    (date(2026, 3, 20), "春分"),
])
def test_current_sekki(d, name):
    assert seed.current_sekki(d) == name


def test_reset_desk_renames_existing(tmp_path):
    desk = tmp_path / "vol-003"
    desk.mkdir()
    (desk / "01_kikaku.json").write_text("{}", encoding="utf-8")

    seed.reset_desk(desk, "20260720")

    assert not desk.exists()
    assert (tmp_path / "vol-003-retry-20260720" / "01_kikaku.json").exists()


def test_reset_desk_avoids_collision(tmp_path):
    (tmp_path / "vol-003-retry-20260720").mkdir()
    desk = tmp_path / "vol-003"
    desk.mkdir()

    seed.reset_desk(desk, "20260720")

    assert (tmp_path / "vol-003-retry-20260720-2").exists()


def test_reset_desk_noop_when_missing(tmp_path):
    seed.reset_desk(tmp_path / "vol-003", "20260720")  # 例外にならないこと


def test_build_seed_with_headlines():
    text = seed.build_seed(3, date(2026, 7, 20), ["見出しA", "見出しB"])
    assert "vol.003" in text
    assert "- 見出しA" in text
    assert "文月" in text
    assert "(月)" in text


def test_build_seed_without_headlines():
    text = seed.build_seed(3, date(2026, 7, 20), [])
    assert "取得できず" in text


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>NHK NEWS</title>
<item><title>headline one</title></item>
<item><title>headline two</title></item>
</channel></rss>"""


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit=-1):
        return RSS


def test_fetch_headlines_parses_rss(monkeypatch):
    monkeypatch.setattr(seed.urllib.request, "urlopen",
                        lambda req, timeout: FakeResponse())
    assert seed.fetch_headlines() == ["headline one", "headline two"]


def test_fetch_headlines_returns_empty_on_error(monkeypatch):
    def boom(req, timeout):
        raise OSError("network down")
    monkeypatch.setattr(seed.urllib.request, "urlopen", boom)
    assert seed.fetch_headlines() == []


def test_main_creates_desk_and_prints_outputs(tmp_path, monkeypatch, capsys):
    (tmp_path / "editorial").mkdir()
    (tmp_path / "editorial" / "daicho.md").write_text(DAICHO, encoding="utf-8")
    monkeypatch.setattr(seed, "fetch_headlines", lambda: [])

    seed.main(tmp_path)

    out = capsys.readouterr().out
    assert "vol=3" in out
    assert "nnn=003" in out
    assert (tmp_path / "desk" / "vol-003" / "seed.md").exists()
