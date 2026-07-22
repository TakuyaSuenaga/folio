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


def test_goudata_image_url_is_recognized_as_known_resource():
    # Arrange: Places写真(googleusercontentのキー無しURL。許可ホストリストには無い)を
    # image に持つ item と、それを src で参照するゲラ
    d, html = load_fixture()
    photo_url = "https://lh3.googleusercontent.com/places/abc123=w1200"
    d["items"][0]["image"] = {
        "url": photo_url,
        "source": "google-places",
        "attributions": [{"name": "撮影者", "uri": "https://maps.google.com/x"}],
    }
    html_with_img = html.replace(
        "</body>", f'<img src="{photo_url}" alt="写真"></body>')

    # Act
    machine = kousei_machine.build_machine(d, html_with_img, check_urls=False)

    # Assert: goudataのimage.urlはknown扱いでunknown_externalに入らない
    assert photo_url not in machine["links_detail"]["unknown_external"]
    assert machine["links_ok"] is True


def test_image_url_not_in_goudata_still_flagged_as_unknown():
    # Arrange: JSONに載っていない画像srcはknownにならず弾かれる(host直書き許可ではない)
    d, html = load_fixture()
    rogue = "https://lh3.googleusercontent.com/rogue=w1200"
    html_with_img = html.replace(
        "</body>", f'<img src="{rogue}" alt="x"></body>')

    # Act
    machine = kousei_machine.build_machine(d, html_with_img, check_urls=False)

    # Assert
    assert machine["links_ok"] is False
    assert rogue in machine["links_detail"]["unknown_external"]


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


def test_escaped_ampersand_in_essay_matches_html_escaped_form():
    # Arrange: essayに&が入り、ADがHTMLエスケープして組んだ場合
    d, html = load_fixture()
    essay_with_amp = d["items"][0]["essay"] + "冷&熱"
    d["items"][0]["essay"] = essay_with_amp
    html_escaped = html.replace("</body>", f"<p>{essay_with_amp.replace('&', '&amp;')}</p></body>")

    # Act
    machine = kousei_machine.build_machine(d, html_escaped, check_urls=False)

    # Assert: エスケープ版でも一致するので偽陽性にならない
    assert machine["genko_match"] is True


def test_rel_attribute_order_does_not_break_sponsored_count():
    # Arrange: rel属性値の順序が「noopener sponsored」でも許容する
    d, html = load_fixture()
    html_reordered = html.replace(
        'rel="sponsored noopener"', 'rel="noopener sponsored"')

    # Act
    machine = kousei_machine.build_machine(d, html_reordered, check_urls=False)

    # Assert
    assert machine["pr_labels_ok"] is True


def test_javascript_scheme_href_fails_links_ok():
    # Arrange: 危険スキーム(javascript:)を仕込んだ悪意あるリンク
    d, html = load_fixture()
    html_with_js = html.replace(
        "</body>", '<a href="javascript:alert(1)">x</a></body>')

    # Act
    machine = kousei_machine.build_machine(d, html_with_js, check_urls=False)

    # Assert
    assert machine["links_ok"] is False
    assert "javascript:alert(1)" in machine["links_detail"]["unsafe_schemes"]


def test_uppercase_script_tag_fails_html_ok():
    # Arrange: 大文字の<SCRIPT>タグ(HTMLとしては等価に実行される)
    d, html = load_fixture()
    evil = html.replace("</body>", "<SCRIPT>alert(1)</SCRIPT></body>")

    # Act
    machine = kousei_machine.build_machine(d, evil, check_urls=False)

    # Assert
    assert machine["html_ok"] is False


def test_single_quoted_javascript_href_fails_links_ok():
    # Arrange: シングルクォート属性のjavascript:スキーム
    d, html = load_fixture()
    evil = html.replace("</body>", "<a href='javascript:alert(1)'>x</a></body>")

    # Act
    machine = kousei_machine.build_machine(d, evil, check_urls=False)

    # Assert
    assert machine["links_ok"] is False
    assert "javascript:alert(1)" in machine["links_detail"]["unsafe_schemes"]


def test_entity_encoded_javascript_scheme_fails_links_ok():
    # Arrange: javascript&#58; はブラウザが実体参照を復号して実行するため検出対象
    d, html = load_fixture()
    evil = html.replace("</body>", '<a href="javascript&#58;alert(1)">x</a></body>')

    # Act
    machine = kousei_machine.build_machine(d, evil, check_urls=False)

    # Assert
    assert machine["links_ok"] is False


def test_uppercase_href_attr_unknown_external_is_flagged():
    # Arrange: HREF=(大文字属性名)でも未知外部リンクとして検出する
    d, html = load_fixture()
    evil = html.replace("</body>", '<a HREF="https://evil.example/x">x</a></body>')

    # Act
    machine = kousei_machine.build_machine(d, evil, check_urls=False)

    # Assert
    assert machine["links_ok"] is False
    assert "https://evil.example/x" in machine["links_detail"]["unknown_external"]


def test_escaped_ampersand_in_known_href_is_not_false_positive():
    # Arrange: クエリ付きURLをADが正しく&amp;でエスケープして組んだ場合
    d, html = load_fixture()
    url = "https://example.com/item?a=1&b=2"
    d["items"][0]["links"].append({"label": "L", "url": url, "sponsored": False})
    html2 = html.replace(
        "</body>",
        '<a href="https://example.com/item?a=1&amp;b=2" rel="noopener">x</a></body>')

    # Act
    machine = kousei_machine.build_machine(d, html2, check_urls=False)

    # Assert: 存在照合も未知外部判定も偽陽性にならない
    assert machine["links_detail"]["present"][url] is True
    assert machine["links_detail"]["unknown_external"] == []
    assert machine["links_ok"] is True


def test_hostless_url_does_not_crash_and_is_flagged():
    # Arrange: ホスト部が空のURL(http:///x)でもクラッシュせず未知扱いにする
    d, html = load_fixture()
    evil = html.replace("</body>", '<a href="http:///x">x</a></body>')

    # Act
    machine = kousei_machine.build_machine(d, evil, check_urls=False)

    # Assert
    assert machine["links_ok"] is False
    assert "http:///x" in machine["links_detail"]["unknown_external"]


def test_inline_event_handler_fails_links_ok():
    # Arrange: インラインイベントハンドラ(scriptタグを使わないJS実行経路)
    d, html = load_fixture()
    evil = html.replace("</body>", '<img src="./x.jpg" onerror="alert(1)"></body>')

    # Act
    machine = kousei_machine.build_machine(d, evil, check_urls=False)

    # Assert
    assert machine["links_ok"] is False
    assert "onerror" in machine["links_detail"]["event_handlers"]


def test_relative_and_hash_and_mailto_hrefs_are_handled():
    # Arrange: 相対パス・#・mailtoが仕様通りに扱われる
    d, html = load_fixture()
    html_with_extra = html.replace(
        "</body>",
        '<a href="./other.html">rel</a>'
        '<a href="#note">hash</a>'
        '<a href="mailto:a@example.com">mail</a></body>')

    # Act
    machine = kousei_machine.build_machine(d, html_with_extra, check_urls=False)

    # Assert: 相対パス・#は許容、mailtoは仕様通り不正扱い
    assert "./other.html" not in machine["links_detail"]["unsafe_schemes"]
    assert "#note" not in machine["links_detail"]["unsafe_schemes"]
    assert "mailto:a@example.com" in machine["links_detail"]["unsafe_schemes"]
