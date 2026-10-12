"""check_glossary_gate — SWE.1 BP3: every domain term defined once, marked and used.

Domain terms are marked _term_ in a requirement's statement and acceptance
criteria. The gate checks that every marked term is defined in the glossary,
that a glossary term is never written without its marks, that no alias is used,
that no term is defined twice (terms and aliases compared without case), and
that every term is used.

    python gates/swe/check_glossary_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_glossary_gate"

# _term_ not glued to a word on either side, so user_id is not a mark
MARK = re.compile(r"(?<![A-Za-z0-9_])_([^_\n]+?)_(?![A-Za-z0-9_])")


@dataclass(frozen=True)
class _Text:
    text: str
    file: str
    line: int
    uid: str


def check(config: ProductConfig) -> list[Finding]:
    glossary = config.relative(config.glossary_file)
    if not config.glossary_file.is_file():
        return [Finding("MISSING_GLOSSARY", glossary, None, "The glossary file does not exist.")]
    findings: list[Finding] = []
    terms, aliases, term_lines = _read_glossary(config, glossary, findings)

    used: set[str] = set()
    for item in _requirement_texts(config):
        for mark in MARK.findall(item.text):
            name = mark.strip().lower()
            if name in terms:
                used.add(name)
            elif name in aliases:
                findings.append(_alias(item, mark, aliases[name]))
            else:
                findings.append(
                    Finding(
                        "UNDEFINED_TERM",
                        item.file,
                        item.line,
                        f"{item.uid}: term _{mark}_ is not defined in the glossary; define it "
                        "once there, or use the defined term.",
                    )
                )
        unmarked = MARK.sub(" ", item.text)
        for name in sorted(terms):
            if _contains(unmarked, name):
                findings.append(
                    Finding(
                        "UNMARKED_TERM",
                        item.file,
                        item.line,
                        f"{item.uid}: glossary term '{terms[name]}' is written without marks; "
                        f"write it as _{terms[name]}_.",
                    )
                )
        for name in sorted(aliases):
            if _contains(unmarked, name):
                findings.append(_alias(item, name, aliases[name]))

    for name, term in sorted(terms.items()):
        if name not in used:
            findings.append(
                Finding(
                    "UNUSED_TERM",
                    glossary,
                    term_lines[name],
                    f"Term '{term}' is used by no requirement; remove it, or use it.",
                )
            )
    return findings


def _read_glossary(config, glossary, findings):
    """Canonical terms and aliases (lower-case → spelling), and each term's line."""
    terms: dict[str, str] = {}
    aliases: dict[str, str] = {}
    term_lines: dict[str, int] = {}
    seen: set[str] = set()
    for block in read_yaml_blocks(config.glossary_file, "glossary_term"):
        if block.error:
            findings.append(Finding("SCHEMA_VIOLATION", glossary, block.line, block.error))
            continue
        violations = validate(block.data, "glossary_term")
        if violations:
            v = violations[0]
            findings.append(
                Finding(
                    "SCHEMA_VIOLATION",
                    glossary,
                    block.key_lines.get(v.path.split("/")[0], block.line),
                    f"'{v.path or 'the block'}' {v.message} (glossary_term.v1).",
                )
            )
            continue
        names = [block.data["term"], *block.data.get("aliases", [])]
        duplicate = next((n for n in names if n.lower() in seen), None)
        if duplicate:
            findings.append(
                Finding(
                    "DUPLICATE_TERM",
                    glossary,
                    block.line,
                    f"'{duplicate}' is defined more than once; keep one definition.",
                )
            )
            continue
        seen.update(n.lower() for n in names)
        term = block.data["term"]
        terms[term.lower()] = term
        term_lines[term.lower()] = block.line
        for alias in block.data.get("aliases", []):
            aliases[alias.lower()] = term
    return terms, aliases, term_lines


def _requirement_texts(config) -> list[_Text]:
    texts = []
    for req in read_requirements(config):
        uid = req.text("uid") or "A requirement"
        statement = req.text("statement")
        if statement:
            texts.append(_Text(statement, req.file, req.line("statement"), uid))
        for criterion in req.data.get("acceptance_criteria") or []:
            if not isinstance(criterion, dict):
                continue
            for key in ("given", "when", "then"):
                value = criterion.get(key)
                if isinstance(value, str):
                    texts.append(_Text(value, req.file, req.line("acceptance_criteria"), uid))
    return texts


def _contains(text: str, name: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text, re.IGNORECASE) is not None


def _alias(item: _Text, alias: str, term: str) -> Finding:
    return Finding(
        "ALIAS_USED",
        item.file,
        item.line,
        f"{item.uid}: '{alias}' is an alias of '{term}'; write _{term}_.",
    )


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
