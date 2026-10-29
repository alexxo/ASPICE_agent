"""tools/render_page_tool.py — the one layout of every page and every decision."""

from tools.render_page_tool import card, card_markdown, card_text, page, section

LINES = {
    "Proposed": "2. stop: it keeps your answer",
    "Question": "What happens next?",
    "Select": ["keep trying", "stop"],
    "Before": "You answered: stop.",
    "Why you": "A security requirement.",
    "Options": "We could keep trying, or stop.",
}


def test_a_card_shows_its_lines_in_the_one_order():
    html = card("open", LINES)
    labels = ["Question", "Why you", "Before", "Options", "Select", "Proposed"]
    places = [html.index(f'<span class="label">{label}</span>') for label in labels]
    assert places == sorted(places)
    assert "<ol><li>keep trying</li><li>stop</li></ol>" in html


def test_other_lines_follow_in_the_order_given():
    html = card("agent", {"Considered": "a or b", "Chosen": "a"}, title="A", action="link")
    assert html.index("Considered") < html.index("Chosen")
    assert '<div class="title"><b>A</b><span>link</span></div>' in html


def test_nothing_is_folded():
    shown = page("T", "lead", "summary", section("S", card("open", LINES)))
    assert "<details" not in shown and "<summary" not in shown
    assert '<p class="summary">summary</p>' in shown


def test_the_terminal_prints_the_same_card():
    text = card_text(LINES, "Y / 1 / 2")
    assert text.splitlines() == [
        "Question: What happens next?",
        "Why you: A security requirement.",
        "Before: You answered: stop.",
        "Options: We could keep trying, or stop.",
        "Select your option: 1. keep trying, 2. stop",
        "Proposed: 2. stop: it keeps your answer",
        "Your answer [Y / 1 / 2]:",
    ]


def test_the_code_host_gets_a_box_per_option():
    text = card_markdown(LINES)
    assert "**Why you:** A security requirement." in text
    assert "- [ ] 1. keep trying\n- [ ] 2. stop" in text
