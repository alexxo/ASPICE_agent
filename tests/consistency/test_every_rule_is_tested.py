"""Layer 2 — every rule a gate can report has a unit test that names it.

Each behaviour is tested once, at the lowest level that shows it (Appendix A.5,
*Fast by design*): a gate's rule belongs to the unit tests. A rule ID that a
gate, a tool or the agent reports in a Finding and that no unit test names is a
rule nobody proves, whatever a scenario walks through.
"""

import re

import pytest

pytestmark = pytest.mark.layer2

REPORTED = re.compile(r'Finding\(\s*"([A-Z][A-Z0-9_]+)"')


def _reported(repo_root) -> dict[str, str]:
    sources = [*repo_root.glob("gates/*/*.py"), *repo_root.glob("tools/*.py")]
    sources += repo_root.glob("agent/*.py")
    rules: dict[str, str] = {}
    for path in sorted(sources):
        for rule in REPORTED.findall(path.read_text()):
            rules.setdefault(rule, path.relative_to(repo_root).as_posix())
    return rules


def test_the_rules_are_found(repo_root):
    assert len(_reported(repo_root)) > 100


def test_every_rule_has_a_unit_test(repo_root):
    unit = "\n".join(p.read_text() for p in (repo_root / "tests/unit").glob("test_*.py"))
    untested = {rule: where for rule, where in _reported(repo_root).items() if rule not in unit}
    assert not untested, f"rules no unit test names: {untested}"
