"""Layer 1 — the WP0 contracts under contracts/ and their examples.

Every contract <name>_contract.v<N>.schema.json has examples under
contracts/examples/<name>/{valid,invalid}/. Asserts: every schema is valid JSON
Schema; every contract has both kinds of example; every valid example passes;
every invalid example fails, and fails for the reason its expect.yaml names
(JSON path + keyword) — so an invalid example cannot pass the suite by breaking
for an unrelated typo.

Markdown contracts (requirement, glossary_term) are validated block by block:
each fenced ```yaml <name> block is one record. An invalid Markdown example
holds exactly one block, so its failure is attributable.
"""

import json
import re

import pytest

yaml = pytest.importorskip("yaml")
jsonschema = pytest.importorskip("jsonschema")
Draft202012Validator = jsonschema.Draft202012Validator

pytestmark = pytest.mark.layer1

CONTRACTS = "contracts"
SUFFIX = re.compile(r"^(?P<name>[a-z_]+)_contract\.v(?P<version>[0-9]+)\.schema\.json$")


class _JsonLoader(yaml.SafeLoader):
    """YAML restricted to the JSON data model: timestamps stay strings.

    PyYAML turns an unquoted 2026-10-03T14:20:00Z into a datetime, which no
    JSON Schema string rule can match. Gates read YAML the same way.
    """


_JsonLoader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _contracts(repo_root):
    base = repo_root / CONTRACTS
    found = ((SUFFIX.match(s.name), s) for s in base.glob("*_contract.v*.schema.json"))
    return sorted((m["name"], s) for m, s in found if m)


def _records(path, name):
    """The records one example file holds, as (label, data) pairs."""
    text = path.read_text()
    if path.suffix == ".md":
        blocks = re.findall(rf"^```yaml {re.escape(name)}\n(.*?)^```$", text, re.M | re.S)
        return [
            (f"{path.name} block {i + 1}", yaml.load(b, _JsonLoader)) for i, b in enumerate(blocks)
        ]
    if path.suffix == ".json":
        return [(path.name, json.loads(text))]
    return [(path.name, yaml.load(text, _JsonLoader))]


def _examples(repo_root, name, kind):
    d = repo_root / CONTRACTS / "examples" / name / kind
    return sorted(p for p in d.glob("*") if p.is_file() and p.name != "expect.yaml")


def _path(error):
    return "/".join(str(p) for p in error.absolute_path)


def test_contracts_exist(repo_root):
    names = [n for n, _ in _contracts(repo_root)]
    for required in (
        "requirement",
        "diagram",
        "invariants",
        "glossary_term",
        "qf",
        "stack",
        "unit",
        "verification_plan",
        "measurements",
        "release",
        "validation",
        "problem",
        "nonconformance",
        "retro_action",
        "change_request",
        "env_variable",
        "findings",
    ):
        assert required in names, f"missing contract {required}"


def test_all_contract_schemas_are_valid_json_schema(repo_root):
    for _name, schema in _contracts(repo_root):
        Draft202012Validator.check_schema(json.loads(schema.read_text()))


def test_every_contract_has_valid_and_invalid_examples(repo_root):
    for name, _ in _contracts(repo_root):
        assert _examples(repo_root, name, "valid"), f"{name}: no valid example"
        assert _examples(repo_root, name, "invalid"), f"{name}: no invalid example"


def test_valid_examples_pass(repo_root):
    for name, schema_path in _contracts(repo_root):
        validator = Draft202012Validator(json.loads(schema_path.read_text()))
        for example in _examples(repo_root, name, "valid"):
            records = _records(example, name)
            assert records, f"{name}/{example.name}: no record found"
            for label, data in records:
                errs = sorted(validator.iter_errors(data), key=str)
                assert not errs, f"{name}/{label}: {_path(errs[0])}: {errs[0].message}"


def test_every_invalid_example_has_an_expectation(repo_root):
    for name, _ in _contracts(repo_root):
        expect_file = repo_root / CONTRACTS / "examples" / name / "invalid" / "expect.yaml"
        assert expect_file.is_file(), f"{name}: invalid/expect.yaml missing"
        expected = set(yaml.load(expect_file.read_text(), _JsonLoader))
        present = {p.name for p in _examples(repo_root, name, "invalid")}
        assert expected == present, (
            f"{name}: expectation drift: no expectation for {present - expected}, "
            f"no example for {expected - present}"
        )


def test_invalid_examples_fail_for_the_expected_reason(repo_root):
    for name, schema_path in _contracts(repo_root):
        validator = Draft202012Validator(json.loads(schema_path.read_text()))
        expect = yaml.load(
            (repo_root / CONTRACTS / "examples" / name / "invalid" / "expect.yaml").read_text(),
            _JsonLoader,
        )
        for example in _examples(repo_root, name, "invalid"):
            records = _records(example, name)
            assert (
                len(records) == 1
            ), f"{name}/{example.name}: needs exactly one record, has {len(records)}"
            label, data = records[0]
            errs = list(validator.iter_errors(data))
            assert errs, f"{name}/{label}: invalid example validated"
            want = expect[example.name]
            got = {(_path(e), e.validator) for e in errs}
            assert (
                (want["path"], want["keyword"]) in got
            ), f"{name}/{label}: expected {want['keyword']} at '{want['path']}', got {sorted(got)}"


def test_suite_vocabulary_is_the_same_in_requirement_and_plan(repo_root):
    """A requirement names a suite; the plan's sections name its command. If the
    two vocabularies drift, a requirement can name a suite no plan can provide.
    The validation suite runs scenarios against a deployed release, never a
    requirement's measurement, so it is the plan's alone."""
    contracts = dict(_contracts(repo_root))
    req = json.loads(contracts["requirement"].read_text())
    plan = json.loads(contracts["verification_plan"].read_text())
    instrument = req["properties"]["measurement_method"]["properties"]["instrument"]["enum"]
    suites = [
        name
        for section in ("unit", "integration", "software", "validation")
        for name in plan["properties"][section]["properties"]["suites"]["propertyNames"]["enum"]
    ]
    expected = [*instrument, "validation"]
    assert sorted(expected) == sorted(suites), f"instrument + validation {expected} != {suites}"


def test_the_readme_lists_every_contract(repo_root):
    """The README's table is how a reader finds a contract; one missing there is
    invisible. Both directions: no row for a contract that does not exist."""
    readme = (repo_root / CONTRACTS / "README.md").read_text()
    listed = set(re.findall(r"^\| `([a-z_]+)\.v[0-9]+` \|", readme, re.M))
    present = {n for n, _ in _contracts(repo_root)}
    assert listed == present, f"README misses {present - listed}, lists unknown {listed - present}"
