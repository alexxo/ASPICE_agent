"""tools/write_stack_table_tool.py — the stack as the architect reads it at checkpoint 3."""

from product_builder import STACK, build_product

from tools.write_stack_table_tool import AREAS, main, stack_table


def test_every_row_is_a_line_the_framework_areas_first():
    rows = [
        {"area": "message_broker", "tool": "rabbitmq", "version": "3.13.7"},
        {"area": "llm", "not_needed": "no text is generated"},
        {"area": "language", "tool": "java", "version": "21"},
        {"area": "ci_cd", "tool": "GitHub Actions"},
    ]
    assert stack_table(rows).splitlines() == [
        "| Area | Tool | Version | Status |",
        "|---|---|---|---|",
        "| language | java | 21 | chosen |",
        "| llm | — | — | not needed: no text is generated |",
        "| ci_cd | GitHub Actions | — | chosen |",
        "| message_broker | rabbitmq | 3.13.7 | chosen |",
    ]


def test_a_cell_cannot_break_the_table():
    table = stack_table([{"area": "llm", "not_needed": "a | b\nc"}])
    assert table.splitlines()[-1] == "| llm | — | — | not needed: a \\| b c |"


def test_the_command_prints_the_products_stack(tmp_path, capsys):
    root = build_product(tmp_path, stack=STACK, git=False)
    assert main(["--root", str(root)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2 + len(STACK["areas"])
    assert [line.split(" | ")[0].removeprefix("| ") for line in lines[2:]] == list(AREAS)


def test_without_a_stack_the_command_fails(tmp_path, capsys):
    root = build_product(tmp_path, git=False)
    assert main(["--root", str(root)]) == 2
    assert "missing or invalid" in capsys.readouterr().err
