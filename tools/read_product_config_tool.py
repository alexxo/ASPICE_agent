"""Read and validate the product's framework configuration, qf.yaml.

Gates and the agent both need to know where the work products live. This tool
reads qf.yaml at the product root, checks it against qf.v1 and resolves every
path under the root, so no gate depends on the agent to find its inputs. A
missing or invalid file is a ConfigError, which a gate turns into a finding and
fails closed on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tools.emit_findings_tool import Finding
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file
from tools.validate_contract_tool import validate

__all__ = ["CONFIG_FILE", "ConfigError", "ProductConfig", "read_product_config"]

CONFIG_FILE = "qf.yaml"


class ConfigError(Exception):
    """qf.yaml is missing (MISSING_CONFIG) or invalid (INVALID_CONFIG)."""

    def __init__(self, rule: str, line: int | None, message: str):
        super().__init__(message)
        self.rule = rule
        self.line = line
        self.message = message

    def to_finding(self) -> Finding:
        return Finding(self.rule, CONFIG_FILE, self.line, self.message)


@dataclass(frozen=True)
class ProductConfig:
    root: Path
    requirements_dir: Path
    glossary_file: Path
    wishes_file: Path
    diagrams_dir: Path
    approvals_dir: Path
    architecture_dir: Path
    decisions_dir: Path
    stack_file: Path
    detailed_design_dir: Path
    code_dir: Path
    verification_plan_file: Path
    env_variables_file: Path
    integration_tests_dir: Path
    software_tests_dir: Path
    observability_dir: Path
    framework_dir: Path
    ci_file: Path
    framework_feedback_file: Path
    releases_dir: Path
    validation_scenarios_dir: Path
    validation_records_dir: Path
    slots: dict[str, str]
    review_agents: tuple[str, ...] = ()
    review_people: tuple[str, ...] = ()  # the people CI calls in for a person's review
    review_architect: str = ""  # who decides every checkpoint, on the host
    customer: str = ""  # on whose behalf the architect accepts a release
    config_items: tuple[str, ...] = ()  # the product's own, added to the framework's
    urgent_approvers: tuple[str, ...] = ()
    change_approvers: tuple[str, ...] = ()
    escalate_after_days: int = 30
    plugins: dict[str, dict] = field(default_factory=dict)  # external plugins, pinned

    def relative(self, path: Path) -> str:
        """The repository-relative path findings use."""
        try:
            return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return Path(path).as_posix()


def read_product_config(root: Path) -> ProductConfig:
    root = Path(root)
    file = root / CONFIG_FILE
    if not file.is_file():
        raise ConfigError("MISSING_CONFIG", None, f"No {CONFIG_FILE} at the product root ({root}).")
    try:
        data = read_yaml_file(file)
    except YamlReadError as err:
        raise ConfigError("INVALID_CONFIG", err.line, f"Not valid YAML: {err.message}.") from err
    violations = validate(data, "qf")
    if violations:
        first = violations[0]
        raise ConfigError(
            "INVALID_CONFIG",
            None,
            f"Breaks qf.v1 at '{first.path or 'the file'}': {first.message}.",
        )
    paths = data["paths"]
    return ProductConfig(
        root=root,
        requirements_dir=root / paths["requirements_dir"],
        glossary_file=root / paths["glossary_file"],
        wishes_file=root / paths["wishes_file"],
        diagrams_dir=root / paths["diagrams_dir"],
        approvals_dir=root / paths["approvals_dir"],
        architecture_dir=root / paths["architecture_dir"],
        decisions_dir=root / paths["decisions_dir"],
        stack_file=root / paths["stack_file"],
        detailed_design_dir=root / paths["detailed_design_dir"],
        code_dir=root / paths["code_dir"],
        verification_plan_file=root / paths["verification_plan_file"],
        env_variables_file=root / paths["env_variables_file"],
        integration_tests_dir=root / paths["integration_tests_dir"],
        software_tests_dir=root / paths["software_tests_dir"],
        observability_dir=root / paths["observability_dir"],
        framework_dir=root / paths["framework_dir"],
        ci_file=root / paths["ci_file"],
        framework_feedback_file=root / paths["framework_feedback_file"],
        releases_dir=root / paths["releases_dir"],
        validation_scenarios_dir=root / paths["validation_scenarios_dir"],
        validation_records_dir=root / paths["validation_records_dir"],
        slots=dict(data["slots"]),
        review_agents=tuple(data["review"]["agents"]),
        review_people=tuple(data["review"]["people"]),
        review_architect=data["review"]["architect"],
        customer=data["customer"],
        config_items=tuple(data.get("config_items") or ()),
        urgent_approvers=tuple(data["urgent_approvers"]),
        change_approvers=tuple(data["change_approvers"]),
        escalate_after_days=data["escalate_after_days"],
        plugins=dict(data.get("plugins") or {}),
    )
