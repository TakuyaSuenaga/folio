from pathlib import Path


WORKFLOW = (Path(__file__).resolve().parents[1] / ".github" / "workflows"
            / "daily-issue.yml").read_text(encoding="utf-8")


def test_failed_generation_is_saved_as_artifact_not_pushed():
    generate, finalize = WORKFLOW.split("\n  finalize:", 1)
    assert "actions/upload-artifact@v4" in generate
    assert "git push" not in generate
    assert "git push" in finalize


def test_finalize_checks_out_latest_main_and_retries_push():
    _, finalize = WORKFLOW.split("\n  finalize:", 1)
    assert "ref: main" in finalize
    assert "git rebase origin/main" in finalize
    assert "for attempt in 1 2 3" in finalize


def test_failure_reporting_runs_after_generate_and_finalize():
    assert "needs: [generate, finalize]" in WORKFLOW
    assert "needs.finalize.result == 'failure'" in WORKFLOW


def test_llm_does_not_generate_final_html_or_copy_candidate_metadata():
    assert "03_draft.json" in WORKFLOW
    assert "python scripts/hydrate_genko.py" in WORKFLOW
    assert "python scripts/render_issue.py" in WORKFLOW
    assert "HTMLは書かず" in WORKFLOW
    assert "後続工程が安全な既定値で補完する" in WORKFLOW
