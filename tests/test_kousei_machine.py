import json
from pathlib import Path

import kousei_machine

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vol-002"


def load_fixture():
    d = json.loads((FIXTURES / "05_goudata.json").read_text(encoding="utf-8"))
    html = (FIXTURES / "vol-002.html").read_text(encoding="utf-8")
    return d, html


def test_vol002_passes_all_checks():
    d, html = load_fixture()
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    assert machine["genko_match"] is True
    assert machine["links_ok"] is True
    assert machine["pr_labels_ok"] is True
    assert machine["html_ok"] is True
    assert machine["okuzuke_ok"] is True
    assert machine["url_status"].startswith("skip")


def test_tampered_essay_fails_genko_match():
    d, html = load_fixture()
    d["items"][0]["essay"] = d["items"][0]["essay"] + "改変"
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    assert machine["genko_match"] is False


def test_unknown_external_link_fails_links_ok():
    d, html = load_fixture()
    html = html.replace("</body>", '<a href="https://evil.example/x">x</a></body>')
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    assert machine["links_ok"] is False
    assert "https://evil.example/x" in machine["links_detail"]["unknown_external"]


def test_check_urls_records_measured_status(monkeypatch):
    d, html = load_fixture()
    monkeypatch.setattr(kousei_machine.verify_links, "check_url", lambda u: 200)
    machine = kousei_machine.build_machine(d, html, check_urls=True)
    assert isinstance(machine["url_status"], list)
    assert all(e["status"] == 200 for e in machine["url_status"])


def test_main_writes_output(tmp_path, monkeypatch):
    monkeypatch.delenv("FOLIO_CHECK_URLS", raising=False)
    out = tmp_path / "machine.json"
    kousei_machine.main(str(FIXTURES / "05_goudata.json"),
                        str(FIXTURES / "vol-002.html"), str(out))
    machine = json.loads(out.read_text(encoding="utf-8"))
    assert machine["genko_match"] is True
