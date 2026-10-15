"""agent/count_retries_tool.py — first run plus 3 retries, then the architect."""

from agent.count_retries_tool import MAX_RETRIES, decide, record_attempt, reset

PASS = [{"gate": "check_glossary_gate", "result": "pass", "findings": []}]


def _fail(n):
    finding = {
        "gate": "check_glossary_gate",
        "rule": "UNDEFINED_TERM",
        "file": "f.md",
        "line": n,
        "message": f"attempt {n}",
    }
    return [{"gate": "check_glossary_gate", "result": "fail", "findings": [finding]}]


def test_three_retries_are_allowed():
    assert MAX_RETRIES == 3


def test_a_passing_attempt_passes(tmp_path):
    record_attempt(tmp_path, "requirements", PASS)
    assert decide(tmp_path, "requirements")["decision"] == "pass"


def test_failures_are_retried_until_three_retries_are_used(tmp_path):
    for n in range(1, 4):
        record_attempt(tmp_path, "requirements", _fail(n))
        state = decide(tmp_path, "requirements")
        assert (state["decision"], state["retries_left"]) == ("retry", 4 - n)


def test_the_fourth_failure_escalates_with_every_attempt(tmp_path):
    for n in range(1, 5):
        record_attempt(tmp_path, "requirements", _fail(n))
    state = decide(tmp_path, "requirements")
    assert (state["decision"], state["attempts"]) == ("escalate", 4)
    report = (tmp_path / state["escalation_report"]).read_text()
    assert all(f"attempt {n}" in report for n in range(1, 5))


def test_a_retry_that_passes_ends_the_loop(tmp_path):
    record_attempt(tmp_path, "requirements", _fail(1))
    record_attempt(tmp_path, "requirements", PASS)
    state = decide(tmp_path, "requirements")
    assert (state["decision"], state["attempts"]) == ("pass", 2)


def test_attempts_are_logged_under_qf(tmp_path):
    record_attempt(tmp_path, "requirements", _fail(1))
    assert (tmp_path / ".qf/attempts/requirements/attempt-1.json").is_file()


def test_reset_starts_a_new_round(tmp_path):
    record_attempt(tmp_path, "requirements", _fail(1))
    reset(tmp_path, "requirements")
    assert decide(tmp_path, "requirements")["attempts"] == 0


def test_a_stage_number_and_its_id_share_one_counter(tmp_path, capsys):
    from agent.count_retries_tool import main

    record_attempt(tmp_path, "diagram", _fail(1))
    assert main(["decide", "--stage", "1", "--root", str(tmp_path)]) == 0
    assert '"attempts": 1' in capsys.readouterr().out
    assert main(["decide", "--stage", "nine", "--root", str(tmp_path)]) == 2
