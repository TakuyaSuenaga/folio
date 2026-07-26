import json

import kousei_machine
import render_issue


def goudata():
    return {
        "issue": {"vol": 9, "date": "2026-07-26", "title": "<更新>",
                  "lead": "安全&確実", "spot_color": "#123456"},
        "items": [{
            "genre": "book", "title": "<本>", "creator": "著者", "year": None,
            "publisher": "", "meta": {}, "essay": "本文<script>",
            "image": {
                "url": "https://lh3.googleusercontent.com/x",
                "source": "google-places",
                "attributions": [{"name": "撮影者", "uri": "https://maps.google.com/x"}],
            },
            "links": [{"label": "購入", "url": "https://books.rakuten.co.jp/x?a=1&b=2",
                       "sponsored": True}],
        }],
    }


def test_render_escapes_content_and_passes_machine_gate():
    d = goudata()
    html = render_issue.render(
        d, {"spot_color": "#abcdef", "cover_layout": "grid",
            "columns": 2, "reverse_data": False})
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    assert "a=1&amp;b=2" in html
    assert "Powered by Google" in html
    machine = kousei_machine.build_machine(d, html, check_urls=False)
    kousei_machine.assert_publishable(machine)


def test_invalid_design_values_are_normalized():
    design = render_issue.normalize_design({
        "spot_color": "red", "cover_layout": "unknown",
        "columns": 9, "reverse_data": "yes",
    })
    assert design == {
        "spot_color": "#1740C8", "cover_layout": "type",
        "columns": 1, "reverse_data": False,
    }


def test_lead_final_is_rendered_instead_of_original():
    html = render_issue.render(goudata(), {}, lead_final="確定リード")
    assert "確定リード" in html
    assert "安全&amp;確実" not in html


def test_main_creates_default_design_when_ad_does_not_write(tmp_path):
    goudata_path = tmp_path / "05_goudata.json"
    design_path = tmp_path / "design.json"
    gera_path = tmp_path / "gera.html"
    goudata_path.write_text(json.dumps(goudata(), ensure_ascii=False), encoding="utf-8")

    render_issue.main([str(goudata_path), str(design_path), str(gera_path)])

    assert json.loads(design_path.read_text(encoding="utf-8")) == {
        "spot_color": "#123456",
        "cover_layout": "type",
        "columns": 1,
        "reverse_data": False,
    }
    assert "<!DOCTYPE html>" in gera_path.read_text(encoding="utf-8")


def test_main_replaces_malformed_or_non_object_design(tmp_path):
    goudata_path = tmp_path / "05_goudata.json"
    goudata_path.write_text(json.dumps(goudata(), ensure_ascii=False), encoding="utf-8")

    for content in ("{broken", "[]"):
        design_path = tmp_path / "design.json"
        gera_path = tmp_path / "gera.html"
        design_path.write_text(content, encoding="utf-8")

        render_issue.main([str(goudata_path), str(design_path), str(gera_path)])

        assert json.loads(design_path.read_text(encoding="utf-8"))["cover_layout"] == "type"
