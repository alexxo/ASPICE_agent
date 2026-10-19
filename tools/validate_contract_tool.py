"""Check a record against one of the framework's contracts.

A contract is contracts/<name>_contract.v<N>.schema.json in this tree, one version
of each. The result
is a list of violations — JSON path, the schema keyword that failed, and the
message — in a fixed order, so the same record always gives the same findings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

__all__ = ["ContractNotFound", "Violation", "contract_path", "validate"]

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"


class ContractNotFound(LookupError):
    """No contracts/<name>_contract.v<N>.schema.json in this tree."""


@dataclass(frozen=True, order=True)
class Violation:
    path: str  # "a/0/b"; empty for the record itself
    keyword: str
    message: str


def contract_path(name: str) -> Path:
    found = sorted(CONTRACTS.glob(f"{name}_contract.v*.schema.json"))
    return found[-1] if found else CONTRACTS / f"{name}_contract.v1.schema.json"


@cache
def _validator(name: str) -> Draft202012Validator:
    path = contract_path(name)
    if not path.is_file():
        raise ContractNotFound(f"no contract '{name}' ({path.name}) in {CONTRACTS}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate(record: Any, name: str) -> list[Violation]:
    """All violations of the contract by the record, sorted; empty when valid."""
    errors = _validator(name).iter_errors(record)
    return sorted(
        Violation("/".join(str(p) for p in e.absolute_path), str(e.validator), e.message)
        for e in errors
    )
