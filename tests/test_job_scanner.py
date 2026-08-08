from scripts import run_job_scanner


def _result(status="partial"):
    return {
        "status": status,
        "source_count": 2,
        "successful_sources": 1,
        "failed_sources": 1,
        "matched_count": 4,
        "inserted_count": 2,
        "failures": [
            {"source": "greenhouse:removed-board", "error": "HTTP Error 404"}
        ],
    }


def test_source_outage_emits_warning_but_scanner_completes(monkeypatch, capsys):
    monkeypatch.setattr(run_job_scanner, "run_due_company_scans", lambda: _result())

    run_job_scanner._run_once()

    output = capsys.readouterr().out
    assert "::warning title=Career source unavailable::" in output
    assert "Scan complete: 1/2 sources" in output


def test_scanner_writes_action_summary(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    run_job_scanner._write_github_summary(_result())

    contents = summary.read_text()
    assert "Status: **partial**" in contents
    assert "greenhouse:removed-board" in contents
