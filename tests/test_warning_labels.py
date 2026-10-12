from noesis.ingest.warnings import extract_warnings, MAX_WARNING_CHARS

PATH = "3 Maintenance > 3.2 Bearings"


def make(*texts, path=PATH, page=1):
    return extract_warnings(
        [
            {
                "page": page,
                "text": text,
                "section_path": path,
                "heading_level": None,
                "char_start": index * 100,
                "char_end": index * 100 + len(text),
            }
            for index, text in enumerate(texts)
        ]
    )


def test_label_with_text_on_the_same_line():
    [block] = make("WARNING: Lock out power before work")

    assert block["label"] == "WARNING"
    assert block["text"] == "Lock out power before work"


def test_standalone_label_collects_following_lines_until_next_label():
    first, second = make(
        "WARNING",
        "Lock out power.",
        "Wait for rotation to stop.",
        "CAUTION: Hot surface",
    )

    assert first["text"] == "Lock out power. Wait for rotation to stop."
    assert second["label"] == "CAUTION"
    assert second["text"] == "Hot surface"


def test_notice_is_a_label():
    [block] = make("NOTICE", "Use only approved lubricant.")

    assert block["label"] == "NOTICE"


def test_signal_word_inside_prose_is_not_a_warning():
    assert make("DANGER tag must be attached by the authorized employee.") == []
    assert make("There is a danger of overheating.") == []


def test_label_without_text_is_dropped():
    assert make("WARNING") == []


def test_safety_scope_is_the_plain_section_path():
    [block] = make("WARNING: Lock out power")

    assert block["safety_scope"] == PATH
    assert block["safety_scope"] == block["section_path"]


def test_signal_word_legend_is_skipped_but_real_warning_is_kept():
    legend = "1 Safety > 1.2 Definitions"
    real = "1 Safety > 1.4 General precautions"
    text = "WARNING: Indicates a hazardous situation"

    assert make(text, path=legend) == []
    assert len(make(text, path=real)) == 1
    
    
def test_block_stops_at_a_numbered_step():
    [block] = make("NOTICE:", "Use the same end.", "5.", "Grout the base plate.")

    assert block["text"] == "Use the same end."


def test_block_stops_at_a_numbered_step_on_the_same_line():
    [block] = make("NOTICE:", "Mark the caps.", "1. Remove the cover.")

    assert block["text"] == "Mark the caps."


def test_block_is_capped_at_a_line_boundary():
    [block] = make("WARNING:", *["x" * 300] * 5)

    assert len(block["text"]) <= MAX_WARNING_CHARS
    assert block["text"] == " ".join(["x" * 300] * 2)