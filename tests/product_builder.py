"""Build a small, complete product on disk for gate and scenario tests.

The baseline passes every SWE.1 gate: two Archify diagrams (an architecture and
a feature sequence) with invariants, the wishes, a glossary, and requirements
that cover every node, edge and invariant. A test changes only what it checks —
a requirement, a term, a diagram — and keeps the rest valid, so each failure has
one cause.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

QF = {
    "contract": "qf.v1",
    "paths": {
        "requirements_dir": "docs/requirements",
        "glossary_file": "docs/glossary.md",
        "wishes_file": "docs/wishes.md",
        "diagrams_dir": "docs/diagrams",
        "approvals_dir": "docs/approvals",
        "architecture_dir": "docs/architecture",
        "decisions_dir": "docs/decisions",
        "stack_file": "docs/architecture/stack.yaml",
        "detailed_design_dir": "docs/design",
        "code_dir": "src",
        "verification_plan_file": "docs/verification-plan.md",
        "env_variables_file": "docs/configuration.md",
        "integration_tests_dir": "it",
        "software_tests_dir": "st",
        "observability_dir": "observability",
        "framework_dir": ".framework",
        "ci_file": ".github/workflows/quality_gates.yml",
        "framework_feedback_file": "FRAMEWORK_FEEDBACK.md",
        "releases_dir": "releases",
        "validation_scenarios_dir": "validation/scenarios",
        "validation_records_dir": "validation/records",
    },
    "slots": {
        "create_diagram_plugin": "archify",
        "create_requirements_plugin": "quality-framework/derive_requirements_plugin",
        "create_architecture_plugin": "example-method/design",
        "create_detailed_design_plugin": "quality-framework/derive_detailed_design_plugin",
        "create_unit_tests_plugin": "example-method/apply",
        "create_unit_code_plugin": "example-method/apply",
        "create_integration_tests_plugin": "example-method/verify",
        "create_software_tests_plugin": "example-method/verify",
        "review_pull_request_plugin": "quality-framework/derive_review_plugin",
        "create_validation_scenarios_plugin": (
            "quality-framework/derive_validation_scenarios_plugin"
        ),
    },
    "review": {"agents": ["qf-reviewer-bot"], "people": ["lead-bob"]},
    "urgent_approvers": ["lead-bob"],
    "change_approvers": ["lead-bob"],
    "escalate_after_days": 30,
}

ARCHITECTURE = {
    "schema_version": 1,
    "diagram_type": "architecture",
    "meta": {"title": "Auth flow", "output": "auth-flow.html"},
    "components": [
        {"id": "web-app", "type": "frontend", "label": "Web app"},
        {"id": "auth-service", "type": "backend", "label": "Auth service"},
    ],
    "connections": [
        {"id": "signin-request", "from": "web-app", "to": "auth-service", "label": "sign in"},
    ],
}

SEQUENCE = {
    "schema_version": 1,
    "diagram_type": "sequence",
    "meta": {"title": "Login", "output": "login.html"},
    "participants": [
        {"id": "web-app", "type": "frontend", "label": "Web app"},
        {"id": "auth-service", "type": "backend", "label": "Auth service"},
    ],
    "messages": [
        {
            "id": "submit-credentials",
            "from": "web-app",
            "to": "auth-service",
            "y": 160,
            "label": "submit",
        },
        {
            "id": "session-opened",
            "from": "auth-service",
            "to": "web-app",
            "y": 190,
            "label": "session",
        },
    ],
}

INVARIANTS = {
    "login": {
        "diagram": "login",
        "invariants": [
            {
                "id": "INV-1",
                "statement": "After five consecutive failed sign-ins the account is locked.",
                "constrains": ["submit-credentials"],
            }
        ],
    }
}

WISHES = [
    {"id": "W-01", "statement": "Users sign in with an email and a password.", "source": "PO"},
    {"id": "W-02", "statement": "Accounts are protected against guessing.", "source": "security"},
    {
        "id": "W-03",
        "statement": "It must run on our Java 21 runtime.",
        "source": "operations",
        "kind": "constraint",
    },
]

WISH_LINKS = {
    "auth-flow": {
        "diagram": "auth-flow",
        "links": {"web-app": ["W-01"], "auth-service": ["W-01"], "signin-request": ["W-01"]},
    },
    "login": {
        "diagram": "login",
        "links": {"web-app": ["W-01"], "auth-service": ["W-01"], "INV-1": ["W-02"]},
    },
}


def _areas(**chosen) -> list[dict]:
    """A row for every area every stack holds: the given ones chosen, the rest not
    needed; the framework's areas name what the fixture's qf.yaml and host use."""
    from tools.write_stack_table_tool import AREAS

    given = {
        "version_control": {"tool": "GitHub"},
        "ci_cd": {"tool": "GitHub Actions"},
        "task_management": {"tool": "GitHub Issues"},
        "requirements_engineering": {"tool": QF["slots"]["create_requirements_plugin"]},
        "diagram_tool": {"tool": QF["slots"]["create_diagram_plugin"]},
    }
    rows = []
    for area in AREAS:
        picked = chosen.get(area, given.get(area))
        if picked is None:
            rows.append({"area": area, "not_needed": "the fixture does without it"})
        for row in picked if isinstance(picked, list) else [picked] if picked else []:
            rows.append({"area": area, **row})
    return rows


STACK = {
    "contract": "stack.v2",
    "areas": _areas(
        language={"tool": "java", "version": "21"},
        frameworks={"tool": "spring-boot", "version": "3.3.4", "purpose": "HTTP API"},
        test_runner={"tool": "maven", "version": "3.9.9", "version_command": "mvn -v"},
        lint={
            "tool": "checkstyle",
            "version": "10.18.2",
            "version_command": "mvn -q checkstyle:help",
            "run": "mvn -q checkstyle:check",
        },
        format={
            "tool": "spotless",
            "version": "2.43.0",
            "version_command": "mvn -q spotless:help",
            "run": "mvn -q spotless:check",
        },
        secrets_scanner={
            "tool": "gitleaks",
            "version": "8.21.2",
            "version_command": "gitleaks version",
            "run": "gitleaks detect --no-banner --report-format sarif "
            "--report-path build/secrets.sarif",
            "results": "build/secrets.sarif",
        },
        dependencies_scanner={
            "tool": "osv-scanner",
            "version": "1.9.1",
            "version_command": "osv-scanner --version",
            "run": "osv-scanner --format sarif --output build/dependencies.sarif -r .",
            "results": "build/dependencies.sarif",
        },
    ),
    "code_files": ["**/*.java"],
    "env_read_patterns": [r'System\.getenv\("([A-Z0-9_]+)"\)'],
    "decision_record": "docs/decisions/0001-java-for-the-auth-service.md",
}

DECISIONS = {
    "0001-java-for-the-auth-service": {
        "id": "ADR-0001",
        "title": "Java 21 for the auth service",
        "status": "accepted",
        "date": "2026-10-05",
        "context": "The customer runs Java 21 only.",
        "options": [
            {"name": "Java 21", "pros": ["customer runtime"], "cons": ["memory"]},
            {"name": "Go", "pros": ["small"], "cons": ["not operated by the customer"]},
        ],
        "choice": "Java 21",
        "consequences": "256 MB per instance.",
    }
}


def _component(cid, name, meets, **extra):
    budget = [{"resource": "memory", "value": 256, "unit": "MB"}]
    return {
        "id": cid,
        "derived_from": f"auth-flow#{cid}",
        "role": "component",
        "name": name,
        "responsibility": f"The {name.lower()}.",
        "budget": budget,
        "size": "M",
        "meets": meets,
        "modes": {"not_applicable": "One mode; it starts ready."},
        "concurrency": {"not_applicable": "Each request is handled on its own."},
        "composition_root": f"{name.replace(' ', '')}App.main",
        **extra,
    }


ARCHITECTURE_DOC = {
    "components": [
        _component("web-app", "Web app", ["REQ-0049"]),
        _component(
            "auth-service",
            "Auth service",
            ["REQ-0047", "REQ-0048", "REQ-0050", "REQ-0051"],
            decisions=["ADR-0001"],
            modes=[
                {"mode": "normal", "to": ["degraded"]},
                {"mode": "degraded", "to": ["normal"]},
            ],
            concurrency="Sign-ins run in parallel; the failure counter is updated atomically.",
        ),
    ],
    "interfaces": [
        {
            "id": "signin-request",
            "derived_from": "auth-flow#signin-request",
            "from": "web-app",
            "to": "auth-service",
            "external": False,
            "protocol": "HTTPS + JSON",
            "data": "email and password",
            "implementations": {
                "real": "HTTPS client of the auth service",
                "double": {"kind": "stub", "name": "auth service stub"},
            },
        },
    ],
}

GLOSSARY = [
    {"term": "account", "definition": "The record that identifies one registered user."},
    {"term": "lockout", "definition": "The state of an account that refuses every sign-in."},
]


def _req(uid, level, kind, statement, derived_from, refines=None, **extra) -> dict[str, Any]:
    req: dict[str, Any] = {
        "uid": uid,
        "level": level,
        "kind": kind,
        "criticality": "high",
        "statement": statement,
        "acceptance_criteria": [
            {"case": "happy", "given": "the system", "when": "it is used", "then": "it works"},
            {"case": "error", "given": "the system", "when": "it fails", "then": "it reports it"},
        ],
        "feasibility": "Standard technology.",
        "size": "S",
        "environment": "none",
        "derived_from": derived_from,
    }
    if refines:
        req["refines"] = refines
    req.update(copy.deepcopy(extra))  # no dict shared between requirements
    return req


NFR = {
    "metric": "failed sign-ins before lockout",
    "threshold": "<= 5",
    "measurement_method": {"instrument": "integration", "window": "one run", "sample": "10"},
}

REQUIREMENTS = {
    "login": [
        _req(
            "REQ-0011",
            "system",
            "functional",
            "The web app shows a sign-in form.",
            "auth-flow#web-app",
        ),
        _req(
            "REQ-0012",
            "system",
            "functional",
            "A user signs in to their _account_.",
            "auth-flow#auth-service",
        ),
        _req("REQ-0013", "system", "constraint", "The product runs on Java 21.", "W-03"),
        _req(
            "REQ-0014",
            "system",
            "interface",
            "The web app sends the sign-in request.",
            "auth-flow#signin-request",
        ),
        _req(
            "REQ-0047",
            "software",
            "security",
            "Five failed sign-ins cause a _lockout_.",
            "login#INV-1",
            "REQ-0012",
            **NFR,
        ),
        _req(
            "REQ-0048",
            "software",
            "observability",
            "The auth service logs every sign-in.",
            "login#auth-service",
            "REQ-0012",
            **NFR,
            events=["auth.signin.start", "auth.signin.end", "auth.signin.error"],
            watched_by=["alert on sign-in errors"],
        ),
        _req(
            "REQ-0049",
            "software",
            "functional",
            "The form takes an email and a password.",
            "login#web-app",
            "REQ-0011",
        ),
        _req(
            "REQ-0050",
            "software",
            "interface",
            "The auth service accepts JSON over HTTPS.",
            "login#auth-service",
            "REQ-0014",
        ),
        _req(
            "REQ-0051",
            "software",
            "constraint",
            "The auth service targets Java 21.",
            "W-03",
            "REQ-0013",
        ),
    ]
}


def _blocks(tag: str, records: list[dict]) -> str:
    parts = [
        f"```yaml {tag}\n{yaml.safe_dump(r, sort_keys=False, allow_unicode=True)}```"
        for r in records
    ]
    return "# Generated for tests\n\n" + "\n\n".join(parts) + "\n"


def _unit(uid, component, name, inputs=None, outputs=None, **extra) -> dict[str, Any]:
    na = {"range": "not applicable", "unit": "not applicable"}
    return {
        "id": uid,
        "derived_from": f"{component}#{uid}",
        "name": name,
        "responsibility": f"{name}.",
        "inputs": inputs if inputs is not None else [{"name": "request", "type": "Request", **na}],
        "outputs": outputs if outputs is not None else [{"name": "ok", "type": "bool", **na}],
        **extra,
    }


def _structure(component, units, calls) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {"title": component, "output": f"{component}.html"},
        "components": [{"id": u, "type": "backend", "label": u} for u in units],
        "connections": [
            {"id": f"{a}-calls-{b}", "from": a, "to": b, "label": "calls"} for a, b in calls
        ],
    }


def _sequence(component, units, calls) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "diagram_type": "sequence",
        "meta": {"title": component, "output": f"{component}-sequence.html"},
        "participants": [{"id": u, "type": "backend", "label": u} for u in units],
        "messages": [
            {"id": f"{a}-to-{b}", "from": a, "to": b, "y": 100 + 30 * i, "label": "call"}
            for i, (a, b) in enumerate(calls)
        ],
    }


_AUTH_CALLS = [("check-credentials", "count-failures"), ("check-credentials", "open-session")]
_AUTH_UNITS = ["check-credentials", "count-failures", "open-session"]

# The detailed design of the baseline architecture: web-app is one unit (no
# sequence diagram); auth-service three units, one calling the other two.
DETAILED_DESIGN = {
    "web-app": {
        "units": [_unit("signin-form", "web-app", "Shows the sign-in form")],
        "structure": _structure("web-app", ["signin-form"], []),
        "sequence": None,
    },
    "auth-service": {
        "units": [
            _unit(
                "check-credentials",
                "auth-service",
                "Checks the credentials",
                calls=["count-failures", "open-session"],
            ),
            _unit(
                "count-failures",
                "auth-service",
                "Counts failed sign-ins",
                inputs=[
                    {
                        "name": "failed attempts",
                        "type": "int",
                        "range": {"min": 0, "max": 5},
                        "unit": "count",
                    }
                ],
            ),
            _unit("open-session", "auth-service", "Opens a session"),
        ],
        "structure": _structure("auth-service", _AUTH_UNITS, _AUTH_CALLS),
        "sequence": _sequence("auth-service", _AUTH_UNITS, _AUTH_CALLS),
    },
}


def build_product(
    root: Path,
    *,
    requirements: dict[str, list[dict]] | None = None,
    glossary: list[dict] | None = None,
    wishes: list[dict] | None = None,
    diagrams: dict[str, dict] | None = None,
    invariants: dict[str, dict] | None = None,
    wish_links: dict[str, dict] | None = None,
    qf: dict | None = None,
    architecture: dict | None = None,
    stack: dict | None = None,
    decisions: dict[str, dict] | None = None,
    detailed_design: dict[str, dict] | None = None,
    env_variables: list[dict] | None = None,
    pictures: bool = True,
    review_pages: bool = True,
    git: bool = True,
) -> Path:
    """Write the product under root; any argument replaces that part of the baseline.

    The architecture (stack, decision records, components and interfaces) is
    written only when one of architecture, stack or decisions is given — the
    baseline is a product at the end of SWE.1. Every diagram gets a stand-in
    picture, as the diagram plugin renders it, and the requirements review page
    is rendered by the framework's tool (pictures, review_pages: False leaves them out).
    """
    root = Path(root)
    docs = root / "docs"
    (docs / "requirements").mkdir(parents=True, exist_ok=True)
    (docs / "diagrams").mkdir(parents=True, exist_ok=True)
    (docs / "approvals").mkdir(parents=True, exist_ok=True)

    (root / "qf.yaml").write_text(yaml.safe_dump(qf if qf is not None else QF, sort_keys=False))
    reqs = requirements if requirements is not None else copy.deepcopy(REQUIREMENTS)
    for name, records in reqs.items():
        (docs / "requirements" / f"{name}.md").write_text(_blocks("requirement", records))
    terms = glossary if glossary is not None else GLOSSARY
    (docs / "glossary.md").write_text(_blocks("glossary_term", terms))
    (docs / "wishes.md").write_text(_blocks("wish", wishes if wishes is not None else WISHES))
    specs = (
        diagrams
        if diagrams is not None
        else {
            "auth-flow.architecture.json": ARCHITECTURE,
            "login.sequence.json": SEQUENCE,
        }
    )
    for name, spec in specs.items():
        (docs / "diagrams" / name).write_text(json.dumps(spec, indent=2))
        if pictures:
            write_picture(docs / "diagrams" / name)
    for name, data in (wish_links if wish_links is not None else WISH_LINKS).items():
        (docs / "diagrams" / f"{name}.wishes.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False)
        )
    for name, data in (invariants if invariants is not None else INVARIANTS).items():
        (docs / "diagrams" / f"{name}.invariants.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False)
        )
    if architecture is not None or stack is not None or decisions is not None:
        _write_architecture(root, architecture, stack, decisions)
    if detailed_design is not None:
        _write_detailed_design(root, detailed_design)
    if env_variables is not None:
        (docs / "configuration.md").write_text(_blocks("env_variable", env_variables))
    ci = root / (qf if qf is not None else QF)["paths"].get("ci_file", QF["paths"]["ci_file"])
    ci.parent.mkdir(parents=True, exist_ok=True)
    ci.write_text(CI_TEMPLATE.read_text())  # the setup writes it: the always-on gates need it
    if review_pages:
        render_reviews(root)
    if git:
        commit_all(root, "product as built")
    return root


CI_TEMPLATE = Path(__file__).resolve().parents[1] / "templates/github/quality_gates.yml"


def write_picture(spec: Path) -> Path:
    """A stand-in for the page the diagram plugin renders next to its diagram."""
    picture = Path(spec).with_suffix(".html")
    title = f"<title>{picture.name}</title>"
    picture.write_text(f"<!doctype html>\n{title}\n<p>Stand-in picture.</p>\n")
    return picture


def render_reviews(root: Path) -> None:
    """The requirements review page, as the agent renders it before checkpoint 2."""
    from agent.render_review_tool import render_review
    from tools.read_product_config_tool import ConfigError

    try:
        render_review(root)
    except ConfigError:  # a product built with a broken qf.yaml has no page
        return


def baseline_requirements() -> dict[str, list[dict]]:
    return copy.deepcopy(REQUIREMENTS)


STANDIN_SKILLS = {
    "archify": "archify",
    "design": "example-method",
    "apply": "example-method",
    "verify": "example-method",
}


def standin_text(name: str) -> str:
    return f"---\nname: {name}\ndescription: Stand-in for tests.\n---\n"


def install_plugins(root: Path, names: list[str] | None = None) -> None:
    """Install each stand-in skill under root's .agents/skills — as the person would,
    in the product's ignored folder or (root = home) on the machine."""
    for name in names if names is not None else STANDIN_SKILLS:
        skill = Path(root) / ".agents" / "skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(standin_text(name))


def build_installed_product(root: Path, **parts) -> Path:
    """A product with its plugins pinned and installed, ready for the agent."""
    build_product(root, **parts)
    install_plugins(root)
    return Path(root)


def record_stages_done(root: Path, *stage_ids: str) -> None:
    """The stage done records of the stages finished before a scenario starts, as
    the agent writes them (record_stage_done_tool) when a stage's gates first pass."""
    import subprocess

    from agent.read_stages_tool import stage
    from tools.read_product_config_tool import read_product_config

    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    folder = read_product_config(root).approvals_dir
    folder.mkdir(parents=True, exist_ok=True)
    for stage_id in stage_ids:
        s = stage(stage_id)
        record = {"stage": s.id, "number": s.number, "date": "2026-10-04T08:00:00+00:00"}
        record["commit"] = commit
        name = f"2026-10-04T0800{s.number:02d}Z-stage-{s.number}-done.yaml"
        (folder / name).write_text(yaml.safe_dump(record, sort_keys=False))


def commit_all(root: Path, message: str, env: dict[str, str] | None = None) -> None:
    """Make root a git repository (if needed) and commit everything in it; env sets
    e.g. GIT_AUTHOR_DATE and GIT_COMMITTER_DATE."""
    import os
    import subprocess

    run = ["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.org"]
    if not (Path(root) / ".git").exists():
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run([*run, "add", "-A"], check=True)
    subprocess.run(
        [*run, "commit", "-q", "--allow-empty", "-m", message],
        check=True,
        env={**os.environ, **env} if env else None,
    )


def _write_architecture(root: Path, architecture, stack, decisions) -> None:
    arch = Path(root) / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "stack.yaml").write_text(
        yaml.safe_dump(stack if stack is not None else STACK, sort_keys=False)
    )
    doc = architecture if architecture is not None else ARCHITECTURE_DOC
    text = _blocks("component", doc["components"]) + "\n" + _blocks("interface", doc["interfaces"])
    (arch / "auth-flow.md").write_text(text)
    folder = Path(root) / "docs" / "decisions"
    folder.mkdir(parents=True, exist_ok=True)
    for name, record in (decisions if decisions is not None else DECISIONS).items():
        (folder / f"{name}.md").write_text(_blocks("decision", [record]))


def _write_detailed_design(root: Path, design: dict[str, dict]) -> None:
    folder = Path(root) / "docs" / "design"
    folder.mkdir(parents=True, exist_ok=True)
    for component, parts in design.items():
        (folder / f"{component}.md").write_text(_blocks("unit", parts["units"]))
        if parts.get("structure") is not None:
            text = json.dumps(parts["structure"], indent=2)
            (folder / f"{component}.architecture.json").write_text(text)
        if parts.get("sequence") is not None:
            text = json.dumps(parts["sequence"], indent=2)
            (folder / f"{component}.sequence.json").write_text(text)


def detailed_design_doc() -> dict:
    return copy.deepcopy(DETAILED_DESIGN)


def architecture_doc() -> dict:
    return copy.deepcopy(ARCHITECTURE_DOC)


# ── a Python product past the detailed design, for stages 5 and 6 (decision 3) ──
#
# Its stack runs this interpreter's pytest (with pytest-cov) and ruff, so the
# gates run real product commands without a second toolchain. Every unit is a
# module <unit_id>.py with run(value); its test test_<unit_id>.py sits next to it,
# in the component's folder under src/.


def _suite(name: str, folder: str, **extra) -> dict:
    """A suite of the Python product: this interpreter's pytest over one folder."""
    import shlex
    import sys

    py = shlex.quote(sys.executable)
    return {
        "tool": "pytest",
        "run": f"{py} -m pytest -q -p no:cacheprovider --junitxml=build/{name}.xml {folder}",
        "results": f"build/{name}.xml",
        **extra,
        "test_files": ["**/test_*.py"],
    }


SUITES = {
    "unit": _suite("unit", "src", coverage="build/coverage.xml"),
    "integration": _suite("integration", "it"),
    "software": _suite("software", "st/software"),
    "e2e": _suite("e2e", "st/e2e"),
    "bench": _suite("bench", "st/bench", measurements="build/measurements/*.json"),
    "validation": _suite("validation", "validation/scenarios"),
}
SUITES["unit"]["run"] = SUITES["unit"]["run"].replace(
    " src", " --cov=src --cov-report=xml:build/coverage.xml src"
)

PLAN = {
    "contract": "verification_plan.v1",
    "unit": {
        "techniques": ["one test per acceptance criterion"],
        "pass_fail_criteria": "every selected unit test passes",
        "entry_criteria": ["the detailed design is merged"],
        "exit_criteria": ["every unit test passes"],
        "infrastructure": ["pytest"],
        "selection": "every unit test on every pull request",
        "regression": "all unit tests run again",
        "coverage": {"metric": "lines", "minimum": 50},
        "suites": {"unit": SUITES["unit"]},
    },
}

# A user outside the product reaches the web app (decision 24): the web app is a
# trust boundary and needs its input-validation tests (decision 25).
PY_ARCHITECTURE = copy.deepcopy(ARCHITECTURE)
PY_ARCHITECTURE["components"].append({"id": "user", "type": "external", "label": "User"})
PY_ARCHITECTURE["connections"].append(
    {"id": "browse", "from": "user", "to": "web-app", "label": "uses"}
)

PY_WISH_LINKS = copy.deepcopy(WISH_LINKS)
PY_WISH_LINKS["auth-flow"]["links"].update({"user": ["W-01"], "browse": ["W-01"]})

PY_REQUIREMENTS = copy.deepcopy(REQUIREMENTS)
PY_REQUIREMENTS["login"][4:4] = [
    _req("REQ-0015", "system", "functional", "A user signs in from a browser.", "auth-flow#user"),
    _req(
        "REQ-0016",
        "system",
        "interface",
        "The web app takes the sign-in form from the browser.",
        "auth-flow#browse",
    ),
]
PY_REQUIREMENTS["login"] += [
    _req(
        "REQ-0052",
        "software",
        "security",
        "The web app rejects a malformed sign-in form.",
        "login#web-app",
        "REQ-0016",
        **NFR,
    ),
    _req(
        "REQ-0053",
        "software",
        "functional",
        "The form opens in any current browser.",
        "login#web-app",
        "REQ-0015",
    ),
]

# The Python product measures its non-functional requirements with a bench
# suite, which writes measurements.v1 (decision 6 of the software verification stage).
for _req_block in PY_REQUIREMENTS["login"]:
    if "measurement_method" in _req_block:
        _req_block["measurement_method"]["instrument"] = "bench"

PY_ARCHITECTURE_DOC = copy.deepcopy(ARCHITECTURE_DOC)
PY_ARCHITECTURE_DOC["components"][0]["meets"] += ["REQ-0052", "REQ-0053"]
PY_ARCHITECTURE_DOC["components"].append(
    {
        "id": "user",
        "derived_from": "auth-flow#user",
        "role": "external",
        "name": "User",
        "responsibility": "Signs in through a browser.",
    }
)
PY_ARCHITECTURE_DOC["interfaces"].append(
    {
        "id": "browse",
        "derived_from": "auth-flow#browse",
        "from": "user",
        "to": "web-app",
        "external": True,
        "protocol": "HTTPS from a browser",
        "data": "the sign-in form and its fields",
        "security_templates": ["input-validation"],
        "implementations": {
            "real": "the browser",
            "double": {"kind": "fake", "name": "scripted browser"},
        },
    }
)

# Declared with the detailed design (decision 23): open-session reads its secret.
ENV_VARIABLES = [
    {
        "name": "SESSION_SECRET",
        "description": "Signs the session cookies.",
        "required": True,
        "example": "change-me",
        "valid": "any non-empty string",
    }
]

PY_GITIGNORE = ".qf/\n.agents/\n.claude/\nbuild/\n.coverage\n__pycache__/\n"

SCANNER_PATH = "scanners/scan.py"
SCANNER = """\
# A stand-in scanner: writes as SARIF the results listed in
# scanners/<kind>.findings.json, or none.
import json, pathlib, sys

if sys.argv[1] == "--version":
    print("fixture-scanner 1.0.0")
    sys.exit(0)
kind, out = sys.argv[1], pathlib.Path(sys.argv[2])
listed = pathlib.Path(f"scanners/{kind}.findings.json")
results = json.loads(listed.read_text()) if listed.exists() else []
out.parent.mkdir(parents=True, exist_ok=True)
sarif = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": kind, "rules": []}},
                                        "results": results}]}
out.write_text(json.dumps(sarif))
"""


def python_stack() -> dict:
    import platform
    import shlex
    import sys
    from importlib import metadata

    py = shlex.quote(sys.executable)
    ruff = {"version": metadata.version("ruff"), "version_command": f"{py} -m ruff --version"}
    scanner = {"version": "1.0.0", "version_command": f"{py} {SCANNER_PATH} --version"}
    return {
        "contract": "stack.v2",
        "areas": _areas(
            language={"tool": "python", "version": platform.python_version()},
            test_runner={
                "tool": "pytest",
                "version": metadata.version("pytest"),
                "version_command": f"{py} -m pytest --version",
            },
            lint={"tool": "ruff", **ruff, "run": f"{py} -m ruff check --no-cache src"},
            format={"tool": "ruff", **ruff, "run": f"{py} -m ruff format --check --no-cache src"},
            **{
                f"{kind}_scanner": {
                    "tool": "fixture-scanner",
                    **scanner,
                    "run": f"{py} {SCANNER_PATH} {kind} build/{kind}.sarif",
                    "results": f"build/{kind}.sarif",
                }
                for kind in ("secrets", "dependencies")
            },
        ),
        "code_files": ["**/*.py"],
        "env_read_patterns": [r"os\.environ\[[\"']([A-Z0-9_]+)[\"']\]"],
        "decision_record": "docs/decisions/0001-java-for-the-auth-service.md",
    }


def edit_plan(root: Path, change) -> None:
    """Change the product's verification plan in place: change(plan) edits the dict."""
    path = Path(root) / QF["paths"]["verification_plan_file"]
    text = path.read_text()
    start = text.index("```yaml verification_plan\n") + len("```yaml verification_plan\n")
    plan = yaml.safe_load(text[start : text.index("```", start)])
    change(plan)
    block = yaml.safe_dump(plan, sort_keys=False)
    path.write_text(f"# Verification plan\n\n```yaml verification_plan\n{block}```\n")


def unit_path(component: str, unit: str, test: bool = False) -> str:
    module = unit.replace("-", "_")
    name = f"test_{module}.py" if test else f"{module}.py"
    return f"src/{component.replace('-', '_')}/{name}"


def write_stub(root: Path, component: str, unit: str) -> None:
    text = f"# @unit[{unit}]\n\n\ndef run(value):\n    return 0\n"
    _write(root, unit_path(component, unit), text)


def write_unit_test(root: Path, component: str, unit: str, assertion: str = "run(1) == 2") -> None:
    module = unit.replace("-", "_")
    text = (
        f"# @unit[{unit}]\nfrom {module} import run\n\n\n"
        f"def test_{module}():\n    assert {assertion}\n"
    )
    _write(root, unit_path(component, unit, test=True), text)


def write_code(root: Path, component: str, unit: str, sdoc: str | None = None) -> None:
    marker = f"# @unit[{unit}]" + (f" @sdoc[{sdoc}]" if sdoc else "")
    text = f"{marker}\n\n\ndef run(value):\n    return value + 1\n"
    _write(root, unit_path(component, unit), text)


def _write(root: Path, relative: str, text: str) -> None:
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def design_units_by_component() -> dict[str, list[str]]:
    return {c: [u["id"] for u in parts["units"]] for c, parts in DETAILED_DESIGN.items()}


def build_python_product(
    root: Path,
    *,
    plan: dict | None = PLAN,
    stack: dict | None = None,
    branch: str | None = "feature/REQ-0047-lockout",
) -> Path:
    """A product at the end of stage 4 with a Python stack and its verification
    plan, committed on main; work continues on a feature branch."""
    import subprocess

    qf = copy.deepcopy(QF)
    qf["slots"]["create_unit_tests_plugin"] = "quality-framework/derive_unit_tests_plugin"
    qf["slots"]["create_unit_code_plugin"] = "quality-framework/derive_unit_code_plugin"
    qf["slots"]["create_integration_tests_plugin"] = (
        "quality-framework/derive_integration_tests_plugin"
    )
    qf["slots"]["create_software_tests_plugin"] = "quality-framework/derive_software_tests_plugin"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(PY_GITIGNORE)
    _write(root, SCANNER_PATH, SCANNER)
    if plan is not None:
        (root / "docs").mkdir(parents=True, exist_ok=True)
        block = yaml.safe_dump(plan, sort_keys=False)
        text = f"# Verification plan\n\n```yaml verification_plan\n{block}```\n"
        (root / qf["paths"]["verification_plan_file"]).write_text(text)
    build_product(
        root,
        qf=qf,
        requirements=copy.deepcopy(PY_REQUIREMENTS),
        diagrams={
            "auth-flow.architecture.json": PY_ARCHITECTURE,
            "login.sequence.json": SEQUENCE,
        },
        wish_links=PY_WISH_LINKS,
        architecture=PY_ARCHITECTURE_DOC,
        stack=stack if stack is not None else python_stack(),
        detailed_design=detailed_design_doc(),
        env_variables=copy.deepcopy(ENV_VARIABLES),
        git=False,
    )
    commit_all(root, "product at the end of stage 4")
    subprocess.run(["git", "-C", str(root), "branch", "-M", "main"], check=True)
    if branch:
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", branch], check=True)
    return root


SETTINGS = "src/auth_service/session_settings.py"
SETTINGS_TEST = "src/auth_service/test_session_settings.py"


def write_settings_stub(root: Path) -> None:
    text = "# @unit[open-session]\n\n\ndef session_secret():\n    return None\n"
    _write(root, SETTINGS, text)


def write_settings_test(root: Path) -> None:
    """The required SESSION_SECRET: start-up stops without it (decision 21)."""
    text = (
        "# @unit[open-session] @env[SESSION_SECRET]\nimport pytest\n"
        "from session_settings import session_secret\n\n\n"
        "def test_session_secret_is_required(monkeypatch):\n"
        '    monkeypatch.delenv("SESSION_SECRET", raising=False)\n'
        "    with pytest.raises(KeyError):\n        session_secret()\n"
    )
    _write(root, SETTINGS_TEST, text)


def write_settings_code(root: Path) -> None:
    text = (
        "# @unit[open-session]\nimport os\n\n\n"
        'def session_secret():\n    return os.environ["SESSION_SECRET"]\n'
    )
    _write(root, SETTINGS, text)


SECURITY_TEST = "src/web_app/test_signin_form_security.py"


def write_security_test(root: Path, template: str = "input-validation") -> None:
    """The web app's boundary test (decision 27), red on its stub like every test."""
    text = (
        f"# @unit[signin-form] @security[{template}]\nfrom signin_form import run\n\n\n"
        "def test_signin_form_rejects_a_malformed_form():\n    assert run(2) == 3\n"
    )
    _write(root, SECURITY_TEST, text)


def write_all_tests_and_stubs(root: Path) -> None:
    for component, units in design_units_by_component().items():
        for unit in units:
            write_stub(root, component, unit)
            write_unit_test(root, component, unit)
    write_settings_stub(root)
    write_settings_test(root)
    write_security_test(root)


def write_all_code(root: Path) -> None:
    for component, units in design_units_by_component().items():
        for unit in units:
            write_code(root, component, unit)
    write_settings_code(root)


# ── stage 7: the assembler's tests, and the code that emits the log events ──
#
# Component and integration tests live under it/ (decision 2 of the integration
# stage) and reach the units through the folders under src/.

INTEGRATION_PLAN = {
    "techniques": ["one component test per component", "one integration test per flow"],
    "pass_fail_criteria": "every component and integration test passes",
    "entry_criteria": ["every unit test passes"],
    "exit_criteria": ["every component, flow and step has a passing test"],
    "infrastructure": ["pytest"],
    "regression": "every test of a changed component runs again",
    "order": [
        {
            "step": "the auth service alone",
            "components": ["auth-service"],
            "preconditions": ["none"],
            "selection": ["auth-service"],
        },
        {
            "step": "the web app joins",
            "components": ["web-app"],
            "preconditions": ["the auth service passes its tests"],
            "selection": ["web-app", "login"],
        },
    ],
    "suites": {"integration": SUITES["integration"]},
}

COMPONENT_UNITS = {"web-app": "signin-form", "auth-service": "check-credentials"}
FLOW_TEST = "it/test_login_flow.py"


def component_test_path(component: str) -> str:
    return f"it/test_{component.replace('-', '_')}_component.py"


def _reach(component: str) -> str:
    folder = component.replace("-", "_")
    return (
        "import pathlib\nimport sys\n\n"
        f'sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src" / "{folder}"))\n'
    )


def write_integration_plan(root: Path) -> None:
    plan = {**copy.deepcopy(PLAN), "integration": copy.deepcopy(INTEGRATION_PLAN)}
    block = yaml.safe_dump(plan, sort_keys=False)
    text = f"# Verification plan\n\n```yaml verification_plan\n{block}```\n"
    _write(root, QF["paths"]["verification_plan_file"], text)


def write_component_test(root: Path, component: str, assertion: str = "run(1) == 2") -> None:
    module = COMPONENT_UNITS[component].replace("-", "_")
    name = component.replace("-", "_")
    text = (
        f"# @component[{component}]\n{_reach(component)}\n"
        f"from {module} import run  # noqa: E402\n\n\n"
        f"def test_{name}_component():\n    assert {assertion}\n"
    )
    _write(root, component_test_path(component), text)


def write_flow_test(root: Path, flow: str = "login") -> None:
    """The login flow, asserting the events of the observability requirement."""
    text = (
        f"# @flow[{flow}] @sdoc[REQ-0048]\nimport logging\n{_reach('auth-service')}\n"
        "from check_credentials import run  # noqa: E402\n\n\n"
        "def _events(caplog):\n    return [r.getMessage() for r in caplog.records]\n\n\n"
        "def test_a_sign_in_logs_its_start_and_end(caplog):\n"
        "    caplog.set_level(logging.INFO)\n    assert run(1) == 2\n"
        '    assert _events(caplog) == ["auth.signin.start", "auth.signin.end"]\n\n\n'
        "def test_a_failed_sign_in_logs_its_error(caplog):\n"
        "    caplog.set_level(logging.INFO)\n    run(-1)\n"
        '    assert "auth.signin.error" in _events(caplog)\n'
    )
    _write(root, FLOW_TEST, text)


def write_all_integration_tests(root: Path) -> None:
    write_integration_plan(root)
    for component in COMPONENT_UNITS:
        write_component_test(root, component)
    write_flow_test(root)


def write_events_code(root: Path) -> None:
    """check-credentials emits the events of REQ-0048 (emit_log_events_skill)."""
    text = (
        "# @unit[check-credentials] @sdoc[REQ-0048]\nimport logging\n\n"
        'log = logging.getLogger("auth")\n\n\n'
        "def run(value):\n"
        '    log.info("auth.signin.start")\n'
        "    if value < 0:\n"
        '        log.error("auth.signin.error")\n'
        "        return 0\n"
        '    log.info("auth.signin.end")\n'
        "    return value + 1\n"
    )
    _write(root, unit_path("auth-service", "check-credentials"), text)


# ── stage 8: the bridge tester's tests, measurements and observability ──
#
# Software-level tests live under st/ (decision 2 of the software verification
# stage): system-level requirements in st/e2e (the e2e suite), software-level
# ones in st/software, and the measured ones in st/bench, which writes
# measurements.v1 (decisions 3, 4 and 6). Constraints need no test.

SOFTWARE_PLAN = {
    "techniques": ["one test per acceptance criterion", "one measurement per threshold"],
    "pass_fail_criteria": "every software-level test passes and every value meets its threshold",
    "entry_criteria": ["every component and integration test passes"],
    "exit_criteria": ["every requirement has a passing test or a measured value"],
    "infrastructure": ["pytest"],
    "selection": "every software-level test before every release",
    "regression": "all software-level tests run again before every release",
    "order": ["software", "bench", "e2e"],
    "suites": {name: SUITES[name] for name in ("software", "e2e", "bench")},
}

E2E_TEST = "st/e2e/test_sign_in_end_to_end.py"
SOFTWARE_TEST = "st/software/test_sign_in_form.py"
BENCH_TEST = "st/bench/test_lockout_bench.py"
OBSERVABILITY = "observability/alerts/signin-errors.yaml"
E2E_REQUIREMENTS = ["REQ-0011", "REQ-0012", "REQ-0014", "REQ-0015", "REQ-0016"]
SOFTWARE_REQUIREMENTS = ["REQ-0049", "REQ-0050", "REQ-0053"]
MEASURED_REQUIREMENTS = ["REQ-0047", "REQ-0048", "REQ-0052"]


def _reach_from_st(component: str) -> str:
    folder = component.replace("-", "_")
    return (
        "import pathlib\nimport sys\n\n"
        f'sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src" / "{folder}"))\n'
    )


def write_software_plan(root: Path) -> None:
    plan = {
        **copy.deepcopy(PLAN),
        "integration": copy.deepcopy(INTEGRATION_PLAN),
        "software": copy.deepcopy(SOFTWARE_PLAN),
    }
    block = yaml.safe_dump(plan, sort_keys=False)
    text = f"# Verification plan\n\n```yaml verification_plan\n{block}```\n"
    _write(root, QF["paths"]["verification_plan_file"], text)


def _marked_test(requirements: list[str], name: str, assertion: str) -> str:
    stamps = " ".join(f"@sdoc[{uid}]" for uid in requirements)
    return (
        f"# {stamps}\n{_reach_from_st('web-app')}\n"
        "from signin_form import run  # noqa: E402\n\n\n"
        f"def test_{name}():\n    assert {assertion}\n"
    )


def write_e2e_test(root: Path, assertion: str = "run(1) == 2") -> None:
    _write(root, E2E_TEST, _marked_test(E2E_REQUIREMENTS, "a_user_signs_in", assertion))


def write_software_test(root: Path, assertion: str = "run(1) == 2") -> None:
    text = _marked_test(SOFTWARE_REQUIREMENTS, "the_form_takes_the_sign_in", assertion)
    _write(root, SOFTWARE_TEST, text)


def write_bench_test(root: Path, value: str = "run(4)") -> None:
    """Measures the failed sign-ins before a lockout and writes them (decision 6)."""
    stamps = " ".join(f"@sdoc[{uid}]" for uid in MEASURED_REQUIREMENTS)
    entries = ", ".join(
        f'{{"requirement": "{uid}", "value": {value}}}' for uid in MEASURED_REQUIREMENTS
    )
    text = (
        f"# {stamps}\nimport json\n{_reach_from_st('web-app')}\n"
        "from signin_form import run  # noqa: E402\n\n\n"
        "def test_failed_sign_ins_before_a_lockout():\n"
        '    folder = pathlib.Path("build/measurements")\n'
        "    folder.mkdir(parents=True, exist_ok=True)\n"
        f"    measured = [{entries}]\n"
        '    data = {"contract": "measurements.v1", "measurements": measured}\n'
        '    (folder / "bench.json").write_text(json.dumps(data))\n'
    )
    _write(root, BENCH_TEST, text)


def write_observability(root: Path) -> None:
    text = "# @sdoc[REQ-0048]\nalert: sign-in errors\n" "expr: rate(auth.signin.error[1m]) > 50\n"
    _write(root, OBSERVABILITY, text)


def write_all_software_tests(root: Path) -> None:
    write_software_plan(root)
    write_e2e_test(root)
    write_software_test(root)
    write_bench_test(root)
    write_observability(root)


# ── the code host (stage 9) ─────────────────────────────────────────────────

HOST_REPO = "acme/login"
FRAMEWORK_REPO = "acme/quality-framework"
AUTHOR = "dev-alice"
AGENT = "qf-reviewer-bot"
PERSON = "lead-bob"
CODEOWNERS = (
    "# Every gate, the framework pin and the architecture need a person's approval.\n"
    "/.github/workflows/ @lead-bob\n"
    "/.gitmodules @lead-bob\n"
    "/docs/architecture/ @lead-bob\n"
)


def git_head(root: Path) -> str:
    import subprocess

    run = ["git", "-C", str(root), "rev-parse", "HEAD"]
    return subprocess.run(run, capture_output=True, text=True, check=True).stdout.strip()


def add_origin(root: Path, repo: str = HOST_REPO) -> None:
    import subprocess

    url = f"https://github.com/{repo}.git"
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", url], check=True)


NO_PERSON = {"person": "none", "findings": []}


def review(
    author: str,
    commit: str,
    state: str = "APPROVED",
    failing=(),
    bot=False,
    items=None,
    record: dict | None = NO_PERSON,
    submitted: str | None = None,
) -> dict:
    """A review as the host records it; the agent's carries the checklist (every
    item, or the items given) and its review record (none when None)."""
    from tools.post_review_tool import CHECKLIST, render

    if author == AGENT:
        body = render(set(failing), items=items or CHECKLIST, record=record)
    else:
        body = "Looks right."
    return {
        "author": author,
        "state": state,
        "commit": commit,
        "body": body,
        "bot": bot,
        "submitted": submitted,
    }


def note(body: str, updated: str, *, author: str = "github-actions[bot]", bot=True, id=1) -> dict:
    """A comment on a pull request's conversation, as the host records it."""
    return {"id": id, "author": author, "body": body, "updated": updated, "bot": bot}


def pull_request(
    number: int,
    head: str,
    *,
    branch: str = "feature/REQ-0047-lockout",
    files=("src/auth_service/lockout.py",),
    reviews=(),
    merged: bool = False,
    commits=(),
    author: str = AUTHOR,
    merged_at: str | None = None,
    notes=(),
) -> dict:
    return {
        "notes": list(notes),
        "number": number,
        "author": author,
        "head": head,
        "branch": branch,
        "files": list(files),
        "reviews": list(reviews),
        "merged": merged,
        "merged_at": merged_at,
        "commits": list(commits),
    }


def write_host(
    path: Path,
    *,
    pulls=(),
    checks: dict | None = None,
    tags: dict | None = None,
    default_branch: str = "main",
    issues=(),
    signs: dict | None = None,
) -> Path:
    """A recorded host for QF_HOST_FILE: the product's repository and the framework's.
    Every pull request's head passed the gates check unless checks says otherwise."""
    pulls = list(pulls)
    data = {
        "repositories": {
            HOST_REPO: {
                "default_branch": default_branch,
                "checks": checks if checks is not None else {p["head"]: ["gates"] for p in pulls},
                "pull_requests": list(pulls),
                "issues": list(issues),
                "signs": dict(signs or {}),
            },
            FRAMEWORK_REPO: {"default_branch": "main", "tags": dict(tags or {})},
        }
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


def make_framework(root: Path, tag: str = "v6.0.0") -> str:
    """A framework repository with one tagged commit; returns that commit."""
    import subprocess

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("The Quality Framework.\n")
    commit_all(root, "framework")
    subprocess.run(["git", "-C", str(root), "tag", tag], check=True)
    return git_head(root)


def add_framework(
    root: Path, framework: Path, path: str = ".framework", message: str = "build: pin the framework"
) -> None:
    """Pin the framework as a git submodule whose recorded URL is on GitHub."""
    import subprocess

    git = ["git", "-C", str(root), "-c", "protocol.file.allow=always"]
    subprocess.run([*git, "submodule", "add", "-q", str(framework), path], check=True)
    url = f"https://github.com/{FRAMEWORK_REPO}.git"
    subprocess.run(
        ["git", "-C", str(root), "config", "-f", ".gitmodules", f"submodule.{path}.url", url],
        check=True,
    )
    commit_all(root, message)


def prepare_delivery(root: Path, workdir: Path, ref: str = "") -> None:
    """What a product needs before its first delivery: its GitHub remote, the
    framework pinned as a released submodule, the CI file, the code owners and
    the framework feedback log naming the framework version. ref (e.g. #1) is
    added to the commit messages."""
    import shutil

    root = Path(root)
    add_origin(root)
    make_framework(Path(workdir) / "framework")
    suffix = f" {ref}" if ref else ""
    add_framework(root, Path(workdir) / "framework", message=f"build: pin the framework{suffix}")
    ci = root / QF["paths"]["ci_file"]
    ci.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "templates/github/quality_gates.yml", ci)
    (root / ".github/CODEOWNERS").write_text(CODEOWNERS)
    (root / QF["paths"]["framework_feedback_file"]).write_text(
        "# Framework feedback\n\n## Log\n\n- No findings for v6.0.0\n"
    )
    commit_all(root, f"chore: the delivery desk{suffix}")


def open_delivery(
    root: Path, workdir: Path, number: int = 1, reviewers=(AGENT,), files=None
) -> Path:
    """The host with the head of root's branch in an open pull request, reviewed
    by reviewers; returns the host file to set as QF_HOST_FILE."""
    import subprocess

    head = git_head(root)
    branch = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    framework = git_head(Path(root) / QF["paths"]["framework_dir"])
    pull = pull_request(
        number,
        head,
        branch=branch,
        reviews=[review(r, head) for r in reviewers],
        **({"files": files} if files is not None else {}),
    )
    return write_host(Path(workdir) / "host.json", pulls=[pull], tags={"v6.0.0": framework})


# ── configuration management (stage 10) ─────────────────────────────────────


def complete_config_items(root: Path, message: str = "chore: every configuration item #1") -> Path:
    """Give every configuration item the product lacks a committed file."""
    from tools.read_product_config_tool import read_product_config
    from tools.write_release_tool import config_items

    root = Path(root)
    for item in config_items(read_product_config(root)):
        path = root / item
        if path.is_file() or (path.is_dir() and any(path.iterdir())):
            continue
        if path.suffix in (".md", ".yaml", ".yml"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {item}\n")
        else:
            path.mkdir(parents=True, exist_ok=True)
            (path / "README.md").write_text(f"# {item}\n")
    commit_all(root, message)
    return root


def tag_release(root: Path, version: str, rev: str = "HEAD", annotated: bool = True) -> None:
    import subprocess

    name = f"v{version}"
    args = ["tag", "-a", name, "-m", f"Release {version}", rev] if annotated else ["tag", name, rev]
    git = ["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.org"]
    subprocess.run([*git, *args], check=True)


# ── validation (stage 11) ───────────────────────────────────────────────────
# A scenario per wish (decision 5 of the validation stage): W-01 and W-03 are
# automated, run by the validation suite; W-02 is a guided demo run by a person.

SCENARIO_TESTS = {
    "W-01": "validation/scenarios/test_sign_in.py",
    "W-03": "validation/scenarios/test_runtime.py",
}
DEMO = "validation/scenarios/guessing-demo.md"
VALIDATION_PLAN = {
    "selection": "every automated scenario, and the guessing demo, before every release",
    "regression": "every scenario of a wish the release touches runs again",
    "scenarios": [
        {
            "scenario": path,
            "technique": technique,
            "pass_fail_criteria": "the customer sees the wish fulfilled",
            "entry_criteria": ["the release deployed to staging"],
            "environment": "staging with realistic data",
        }
        for path, technique in [
            (SCENARIO_TESTS["W-01"], "acceptance test"),
            (DEMO, "guided demo"),
            (SCENARIO_TESTS["W-03"], "acceptance test"),
        ]
    ],
    "suites": {"validation": SUITES["validation"]},
}


def write_scenario_test(root: Path, wish: str, passes: bool = True) -> None:
    name = wish.lower().replace("-", "_")
    text = f"# @wish[{wish}]\n\n\ndef test_{name}_on_staging():\n    assert {passes}\n"
    _write(root, SCENARIO_TESTS[wish], text)


def write_demo(root: Path) -> None:
    text = (
        "# Guided demo — guessing a password\n\n@wish[W-02]\n\n"
        "The operator tries five wrong passwords; the account locks and says so.\n"
    )
    _write(root, DEMO, text)


def write_validation_plan(root: Path) -> None:
    """Add the validation section to the product's plan."""
    edit_plan(root, lambda plan: plan.update(validation=copy.deepcopy(VALIDATION_PLAN)))


def write_all_scenarios(root: Path) -> None:
    for wish in SCENARIO_TESTS:
        write_scenario_test(root, wish)
    write_demo(root)
    write_validation_plan(root)


def build_releasable_product(workdir: Path) -> tuple[Path, Path]:
    """A Python product on main, its framework pinned, every configuration item
    and every scenario committed: ready for its first release. Returns the root
    and the recorded host to set as QF_HOST_FILE."""
    workdir = Path(workdir)
    framework = make_framework(workdir / "framework")
    root = build_python_product(workdir / "product", branch=None)
    add_framework(root, workdir / "framework")
    write_all_scenarios(root)
    complete_config_items(root, "test(validation): a scenario for every wish #1")
    add_origin(root)
    return root, write_host(workdir / "host.json", tags={"v6.0.0": framework})


def propose_release(root: Path, version: str = "1.0.0") -> None:
    """The release pull request's first commit: the record write_release_tool writes."""
    import subprocess

    from tools.write_release_tool import main as write_release

    subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", f"release/v{version}"])
    assert write_release(["--root", str(root)]) == 0
    commit_all(root, f"chore(release): {version} #2")


def record_validation(
    root: Path, results: list[dict], version: str = "1.0.0", commit: str | None = None
) -> Path:
    """Commit the validation record of a run on staging of commit (the head)."""
    path = Path(root) / QF["paths"]["validation_records_dir"] / f"{version}.yaml"
    record = {
        "contract": "validation.v1",
        "version": version,
        "environment": {"name": "staging", "commit": commit or git_head(root)},
        "results": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False))
    commit_all(root, f"chore(release): validation of {version} #2")
    return path


def passed(*paths: str, result: str = "pass") -> list[dict]:
    """Results for scenarios, the demo run by hand, the others automated."""
    return [
        {
            "scenario": p,
            "technique": "guided demo" if p == DEMO else "acceptance test",
            "result": result,
        }
        for p in paths
    ]


ALL_SCENARIOS = [SCENARIO_TESTS["W-01"], DEMO, SCENARIO_TESTS["W-03"]]


# ── issues (stage 12, and SUP.1 at release) ─────────────────────────────────
# Problems, non-conformances and retrospective actions are host issues whose
# body holds one fenced block (decision 1 of the problem resolution stage).

REPORTER = "dev-carol"
BEFORE = "2020-01-01T09:00:00Z"  # before any commit of a test product
AFTER = "2099-01-01T09:00:00Z"  # after any commit of a test product
PROBLEM = {
    "what": "The account locks after three failed sign-ins instead of five.",
    "where": "sign-in page",
    "reproduce": "Sign in with a wrong password three times.",
    "expected": "The fourth attempt is accepted.",
    "actual": "The account is locked.",
    "status": "under-analysis",
    "cause": "The failure counter counts each attempt twice.",
    "impact": {"requirements": ["REQ-0047"], "components": ["auth-service"]},
    "severity": "medium",
}


def comment(author: str, body: str, created: str = AFTER) -> dict:
    return {"author": author, "body": body, "created": created}


def issue(
    number: int,
    label: str,
    record: dict | None,
    *,
    state: str = "open",
    author: str = REPORTER,
    created: str = BEFORE,
    closed: str | None = None,
    labels=(),
    assignees=(),
    comments=(),
) -> dict:
    """A host issue whose body holds the record as its one block (none when None)."""
    tag = {
        "problem": "problem",
        "non-conformance": "nonconformance",
        "change-request": "change_request",
    }.get(label, "retro_action")
    body = (
        f"```yaml {tag}\n{yaml.safe_dump(record, sort_keys=False)}```\n"
        if record is not None
        else "Something is wrong.\n"
    )
    return {
        "number": number,
        "author": author,
        "state": state,
        "created": created,
        "closed": closed,
        "labels": [label, *labels],
        "assignees": list(assignees),
        "body": body,
        "comments": list(comments),
    }


def problem(number: int, **changes) -> dict:
    """A problem issue; keyword arguments change its record (None removes a field)."""
    record = {**copy.deepcopy(PROBLEM), **changes}
    return {k: v for k, v in record.items() if v is not None}


def write_problem_test(root: Path, number: int) -> str:
    """The crack bench: a test marked @problem[number], next to the unit it tests."""
    path = f"src/auth_service/test_problem_{number}.py"
    _write(root, path, f"# @problem[{number}]\n\n\ndef test_problem_{number}():\n    assert True\n")
    return path


CHANGE = {
    "what": "Lock an account after ten failed sign-ins, not five.",
    "initiator": "product owner",
    "reason": "Support handles too many lockouts.",
    "status": "approved",
    "affected": {
        "wishes": ["W-02"],
        "elements": ["login#INV-1"],
        "requirements": ["REQ-0047"],
    },
    "depends_on": [],
    "size": "S",
}


def change(number: int, **changes) -> dict:
    """A change request record; keyword arguments change it (None removes a field)."""
    record = {**copy.deepcopy(CHANGE), **changes}
    return {k: v for k, v in record.items() if v is not None}
