
import pymupdf

from noesis.ingest.pdf import extract_pdf
from noesis.ingest.sections import detect_sections


def create_section_pdf(path):
    document = pymupdf.open()
    page = document.new_page()

    page.insert_text((72, 80), "1 Purpose and limitations", fontsize=14)
    page.insert_text((72, 110), "1.1 Scope", fontsize=12)
    page.insert_text((72, 140), "Scope details.", fontsize=10)
    page.insert_text((72, 170), "1.1.1 Synthetic status", fontsize=11)
    page.insert_text((72, 200), "Synthetic details.", fontsize=10)
    page.insert_text((72, 230), "1.2 Use limitations", fontsize=12)
    page.insert_text((72, 260), "Limitations details.", fontsize=10)

    document.set_toc([
        [1, "1 Purpose and limitations", 1],
        [2, "1.1 Scope", 1],
        [3, "1.1.1 Synthetic status", 1],
        [2, "1.2 Use limitations", 1],
    ])

    document.save(path)
    document.close()


def test_section_paths_follow_bookmark_hierarchy(tmp_path):
    path = tmp_path / "sections.pdf"
    create_section_pdf(path)

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["1 Purpose and limitations"]["heading_level"] == 1
    assert by_text["1.1 Scope"]["section_path"] == (
        "1 Purpose and limitations > 1.1 Scope"
    )
    assert by_text["Scope details."]["section_path"] == (
        "1 Purpose and limitations > 1.1 Scope"
    )
    assert by_text["Synthetic details."]["section_path"] == (
        "1 Purpose and limitations > 1.1 Scope > 1.1.1 Synthetic status"
    )
    assert by_text["Limitations details."]["section_path"] == (
        "1 Purpose and limitations > 1.2 Use limitations"
    )


def test_real_synthetic_manual_has_expected_sections():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["2 Safety"]["heading_level"] == 1
    assert by_text["2.1 General safety"]["heading_level"] == 2
    assert by_text["2.1.1 Energy isolation"]["heading_level"] == 3
    assert by_text["5.2 Elevated vibration"]["section_path"] == (
        "5 Troubleshooting > 5.2 Elevated vibration"
    )


def test_page_title_is_not_detected_as_duplicate_heading():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"

    lines = detect_sections(path, extract_pdf(path))

    page_title = [
        line for line in lines
        if line["text"] == "1. Purpose and limitations"
    ]

    actual_heading = [
        line for line in lines
        if line["text"] == "1 Purpose and limitations"
    ]

    assert len(page_title) == 1
    assert len(actual_heading) == 1
    assert page_title[0]["heading_level"] is None
    assert actual_heading[0]["heading_level"] == 1
    assert page_title[0]["section_path"] == ""
    
    page_title_2 = [
    line for line in lines
    if line["text"] == "2. Safety"]

    assert len(page_title_2) == 1
    assert page_title_2[0]["heading_level"] is None
    assert page_title_2[0]["section_path"] == ""
    
    
def test_running_header_does_not_change_or_inherit_section_path(tmp_path):
    path = tmp_path / "running_header.pdf"
    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text((72, 80), "1 Purpose and limitations", fontsize=14)
    page1.insert_text((72, 110), "1.2 Use limitations", fontsize=12)
    page1.insert_text((72, 140), "Limitations details.", fontsize=10)

    page2 = document.new_page()
    page2.insert_text((72, 40), "SYNTHETIC CENTRIFUGAL PUMP MANUAL", fontsize=9)
    page2.insert_text((72, 80), "2 Safety", fontsize=14)
    page2.insert_text((72, 110), "Safety details.", fontsize=10)

    document.set_toc([
        [1, "1 Purpose and limitations", 1],
        [2, "1.2 Use limitations", 1],
        [1, "2 Safety", 2],
    ])
    document.save(path)
    document.close()

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["SYNTHETIC CENTRIFUGAL PUMP MANUAL"]["heading_level"] is None
    assert by_text["SYNTHETIC CENTRIFUGAL PUMP MANUAL"]["section_path"] == (
        "1 Purpose and limitations > 1.2 Use limitations"
    )
    assert by_text["2 Safety"]["section_path"] == "2 Safety"
    assert by_text["Safety details."]["section_path"] == "2 Safety"
    

def test_unstyled_numbered_body_text_is_not_detected_as_heading(tmp_path):
    path = tmp_path / "numbered_body_text.pdf"
    document = pymupdf.open()
    page = document.new_page()

    page.insert_text((72, 80), "1 Safety", fontsize=16)
    page.insert_text((72, 110), "Safety details.", fontsize=10)

    # These resemble numbered headings but are ordinary body text.
    page.insert_text((72, 150), "375 PSI", fontsize=9)
    page.insert_text((72, 180), "100 RPM", fontsize=9)
    page.insert_text((72, 210), "4 or 24", fontsize=9)
    page.insert_text((72, 240), "42 for left hand rotation.", fontsize=10)
    page.insert_text((72, 270), "3951 Capitol Avenue", fontsize=10)

    document.set_toc([[1, "1 Safety", 1]])
    document.save(path)
    document.close()

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    for text in (
        "375 PSI",
        "100 RPM",
        "4 or 24",
        "42 for left hand rotation.",
        "3951 Capitol Avenue",
    ):
        assert by_text[text]["heading_level"] is None
        assert by_text[text]["section_path"] == "1 Safety"


def test_bold_numbered_heading_without_bookmark_is_detected(tmp_path):
    path = tmp_path / "fallback_heading.pdf"
    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 80),
        "1 Safety",
        fontsize=16,
        fontname="hebo",
    )
    page.insert_text(
        (72, 115),
        "1.1 General precautions",
        fontsize=12,
        fontname="hebo",
    )
    page.insert_text(
        (72, 145),
        "Follow all safety precautions.",
        fontsize=10,
    )

    document.set_toc([[1, "1 Safety", 1]])
    document.save(path)
    document.close()

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["1 Safety"]["heading_level"] == 1
    assert by_text["1.1 General precautions"]["heading_level"] == 2
    assert by_text["1.1 General precautions"]["section_path"] == (
        "1 Safety > 1.1 General precautions"
    )
    assert by_text["Follow all safety precautions."]["section_path"] == (
        "1 Safety > 1.1 General precautions"
    )
    
    
def test_publication_metadata_does_not_create_section_path(tmp_path):
    import pymupdf

    from noesis.ingest.sections import detect_sections

    pdf_path = tmp_path / "publication_metadata.pdf"

    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf_path)

    lines = [
        {
            "page": 1,
            "text": "2002 (Revised)",
            "size": 9.0,
            "bold": True,
            "bbox": (50.0, 50.0, 150.0, 65.0),
            "char_start": 0,
            "char_end": 15,
        },
        {
            "page": 1,
            "text": "1 Safety",
            "size": 14.0,
            "bold": True,
            "bbox": (50.0, 100.0, 150.0, 120.0),
            "char_start": 16,
            "char_end": 24,
        },
    ]

    result = detect_sections(pdf_path, lines)

    assert result[0]["heading_level"] is None
    assert result[0]["section_path"] == ""
    assert result[1]["heading_level"] == 1
    assert result[1]["section_path"] == "1 Safety"



def test_bold_unnumbered_heading_is_detected(tmp_path):
    path = tmp_path / "unnumbered_heading.pdf"
    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 80),
        "Background",
        fontsize=12,
        fontname="hebo",
    )
    page.insert_text(
        (72, 110),
        "How should I use this booklet?",
        fontsize=11,
        fontname="hebo",
    )
    page.insert_text(
        (72, 140),
        "Read the relevant safety information.",
        fontsize=10,
    )

    document.save(path)
    document.close()

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["Background"]["heading_level"] == 1
    assert by_text["Background"]["section_path"] == "Background"

    assert by_text["How should I use this booklet?"]["heading_level"] == 2
    assert by_text["How should I use this booklet?"]["section_path"] == (
        "Background > How should I use this booklet?"
    )

    assert by_text["Read the relevant safety information."]["section_path"] == (
        "Background > How should I use this booklet?"
    )
    
def test_dotted_top_level_heading_and_relative_font_size(tmp_path):
    path = tmp_path / "dotted_numbered_headings.pdf"
    document = pymupdf.open()
    page = document.new_page()

    # Real-manual pattern: numbered headings are slightly larger
    # than body text, but are not bold.
    page.insert_text(
        (72, 80), "4. Vibration Measurement", fontsize=9.3
    )
    page.insert_text(
        (72, 110), "4.1 Overall Vibration Level", fontsize=9.3
    )
    page.insert_text(
        (72, 140), "4.2 Frequency Spectrum", fontsize=9.3
    )
    page.insert_text(
        (72, 170), "The vibration level should be measured regularly.",
        fontsize=8.5,
    )

    document.save(path)
    document.close()

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["4. Vibration Measurement"]["heading_level"] == 1
    assert by_text["4.1 Overall Vibration Level"]["heading_level"] == 2
    assert by_text["4.2 Frequency Spectrum"]["heading_level"] == 2

    assert by_text["4.1 Overall Vibration Level"]["section_path"] == (
        "4 Vibration Measurement > 4.1 Overall Vibration Level"
    )
    assert by_text["The vibration level should be measured regularly."][
        "section_path"
    ] == "4 Vibration Measurement > 4.2 Frequency Spectrum"
    
    
def test_table_values_metadata_and_bullets_are_not_headings(tmp_path):
    path = tmp_path / "false_headings.pdf"
    document = pymupdf.open()
    page = document.new_page()

    # Genuine unnumbered heading.
    page.insert_text(
        (72, 60), "Background", fontsize=12, fontname="hebo"
    )

    # OEM table captions, model codes, form fields, and list fragments.
    false_headings = [
        "Table 1: General Precautions",
        "3x4-8G",
        "Equipment ID: P-101",
        "POSITION / TITLE",
        ". Shutdown of the system is impractical; and",

"3/4x17",
"V",
"DV",
"Equipment: Centrifugal Water Pump",
"Service: Water transfer",
"Observation: The fictional scenario describes vibration",
"Potential Causes: Misalignment or bearing damage",
"Recommended Action: Measure vibration at bearing locations",
"Priority: High",
    ]

    y = 100
    for text in false_headings:
        page.insert_text(
            (72, y), text, fontsize=11, fontname="hebo"
        )
        y += 30

    document.save(path)
    document.close()

    lines = detect_sections(path, extract_pdf(path))
    by_text = {line["text"]: line for line in lines}

    assert by_text["Background"]["heading_level"] == 1

    for text in false_headings:
        matching_lines = [
           line for line in lines
           if line["text"] == text
        ]
        assert matching_lines, f"Extracted line not found: {text!r}"
        assert matching_lines[0]["heading_level"] is None, (
           f"False heading detected: {text}"
        )
        
def test_en_dash_bullet_is_not_detected_as_heading(tmp_path):
    path = tmp_path / "bullet_test.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    lines = [
        {
            "page": 1,
            "text": "OSHA Coverage",
            "size": 14.0,
            "bold": True,
            "bbox": (72, 50, 200, 65),
            "char_start": 0,
            "char_end": 13,
        },
        {
            "page": 1,
            "text": "– Shutdown of the system is impractical; and",
            "size": 11.0,
            "bold": True,
            "bbox": (72, 80, 300, 95),
            "char_start": 14,
            "char_end": 57,
        },
    ]

    result = detect_sections(path, lines)
    by_text = {line["text"]: line for line in result}

    assert by_text["OSHA Coverage"]["heading_level"] == 1
    assert (
        by_text["– Shutdown of the system is impractical; and"][
            "heading_level"
        ]
        is None
    )

def test_split_numbered_heading_is_combined(tmp_path):
    path = tmp_path / "split_heading.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    lines = [
        {
            "page": 1, "text": "4 Starting pump",
            "size": 24.0, "bold": True,
            "bbox": (72, 40, 250, 60),
            "char_start": 0, "char_end": 15,
        },
        {
            "page": 1, "text": "4.3",
            "size": 16.0, "bold": True,
            "bbox": (72, 80, 110, 100),
            "char_start": 16, "char_end": 19,
        },
        {
            "page": 1, "text": "Adjustment of stuffing box gland",
            "size": 16.0, "bold": True,
            "bbox": (72, 105, 350, 125),
            "char_start": 20, "char_end": 52,
        },
        {
            "page": 1, "text": "The gland must be adjusted evenly.",
            "size": 10.0, "bold": False,
            "bbox": (72, 140, 300, 155),
            "char_start": 53, "char_end": 87,
        },
    ]

    result = detect_sections(path, lines)
    by_text = {line["text"]: line for line in result}

    expected_path = (
        "4 Starting pump > "
        "4.3 Adjustment of stuffing box gland"
    )

    assert by_text["4.3"]["heading_level"] == 2
    assert by_text["4.3"]["section_path"] == expected_path
    assert (
        by_text["Adjustment of stuffing box gland"]["heading_level"]
        is None
    )
    assert (
        by_text["Adjustment of stuffing box gland"]["section_path"]
        == expected_path
    )
    assert (
        by_text["The gland must be adjusted evenly."]["section_path"]
        == expected_path
    )
    
def test_table_region_text_is_not_detected_as_heading(tmp_path):
    import pymupdf

    from noesis.ingest.sections import detect_sections

    path = tmp_path / "table_heading.pdf"
    document = pymupdf.open()
    page = document.new_page()
    document.save(path)
    document.close()

    lines = [
        {
            "page": 1,
            "text": "5 Troubleshooting",
            "size": 14.0,
            "bold": True,
            "bbox": (50.0, 50.0, 200.0, 70.0),
            "char_start": 0,
            "char_end": 17,
        },
        {
            "page": 1,
            "text": "Observed condition",
            "size": 12.0,
            "bold": True,
            "bbox": (50.0, 100.0, 180.0, 115.0),
            "char_start": 18,
            "char_end": 36,
        },
    ]

    table_regions = [
        (1, (45.0, 90.0, 500.0, 200.0)),
    ]

    result = detect_sections(
        path,
        lines,
        excluded_regions=table_regions,
    )
    by_text = {line["text"]: line for line in result}

    assert by_text["5 Troubleshooting"]["heading_level"] == 1
    assert by_text["Observed condition"]["heading_level"] is None
    assert by_text["Observed condition"]["section_path"] == (
        "5 Troubleshooting"
    )
def test_heading_inside_broad_false_positive_table_region_is_detected(
    tmp_path,
):
    path = tmp_path / "broad_table_region.pdf"

    with pymupdf.open() as document:
        document.new_page()
        document.save(path)

    lines = [
        {
            "page": 1,
            "text": "4 Vibration Measurement",
            "size": 14.0,
            "bold": True,
            "bbox": (50.0, 50.0, 250.0, 70.0),
            "char_start": 0,
            "char_end": 22,
        },
        {
            "page": 1,
            "text": "5 Examples of Vibration Spectrum",
            "size": 12.0,
            "bold": True,
            "bbox": (50.0, 150.0, 350.0, 170.0),
            "char_start": 23,
            "char_end": 56,
        },
    ]

    result = detect_sections(path, lines)
    by_text = {line["text"]: line for line in result}

    assert by_text["5 Examples of Vibration Spectrum"][
        "heading_level"
    ] == 1
    assert by_text["5 Examples of Vibration Spectrum"][
        "section_path"
    ] == "5 Examples of Vibration Spectrum"
    
    
def test_unbolded_deep_numbered_heading_at_body_size_is_detected(
    tmp_path,
):
    path = tmp_path / "deep_numbered_heading.pdf"

    with pymupdf.open() as document:
        document.new_page()
        document.save(path)

    lines = [
        {
            "page": 1,
            "text": "2 Geometrical Imperfections",
            "size": 12.0,
            "bold": True,
            "bbox": (50.0, 50.0, 300.0, 70.0),
            "char_start": 0,
            "char_end": 27,
        },
        {
            "page": 1,
            "text": "2.2.1 Surface Roughness",
            "size": 8.5,
            "bold": False,
            "bbox": (50.0, 100.0, 250.0, 115.0),
            "char_start": 28,
            "char_end": 51,
        },
        {
            "page": 1,
            "text": "Surface roughness affects vibration.",
            "size": 8.5,
            "bold": False,
            "bbox": (50.0, 120.0, 300.0, 135.0),
            "char_start": 52,
            "char_end": 89,
        },
    ]

    result = detect_sections(path, lines)
    by_text = {line["text"]: line for line in result}

    assert by_text["2.2.1 Surface Roughness"]["heading_level"] == 3
    assert by_text["2.2.1 Surface Roughness"]["section_path"] == (
        "2 Geometrical Imperfections > 2.2.1 Surface Roughness"
    )
    assert by_text["Surface roughness affects vibration."][
        "section_path"
    ] == "2 Geometrical Imperfections > 2.2.1 Surface Roughness"
    


def test_appendix_headings_start_new_top_level_sections(tmp_path):
    path = tmp_path / "appendix_hierarchy.pdf"

    with pymupdf.open() as document:
        document.new_page()
        document.save(path)

    lines = [
        {
            "page": 1,
            "text": "APPENDIX 3 - RELATED DOCUMENTS",
            "size": 12.0,
            "bold": True,
            "bbox": (50.0, 50.0, 350.0, 70.0),
            "char_start": 0,
            "char_end": 31,
        },
        {
            "page": 1,
            "text": "SPIN questions for several industries",
            "size": 11.0,
            "bold": True,
            "bbox": (50.0, 90.0, 350.0, 110.0),
            "char_start": 32,
            "char_end": 68,
        },
        {
            "page": 1,
            "text": "APPENDIX 4 - GLOSSARY",
            "size": 11.0,
            "bold": True,
            "bbox": (50.0, 150.0, 300.0, 170.0),
            "char_start": 69,
            "char_end": 91,
        },
        {
            "page": 1,
            "text": "Annual Unit Improvement",
            "size": 11.0,
            "bold": True,
            "bbox": (50.0, 190.0, 300.0, 210.0),
            "char_start": 92,
            "char_end": 116,
        },
    ]

    result = detect_sections(path, lines)
    by_text = {line["text"]: line for line in result}

    assert by_text["APPENDIX 3 - RELATED DOCUMENTS"][
        "heading_level"
    ] == 1

    assert by_text["SPIN questions for several industries"][
        "section_path"
    ] == (
        "APPENDIX 3 - RELATED DOCUMENTS"
        " > SPIN questions for several industries"
    )

    assert by_text["APPENDIX 4 - GLOSSARY"]["heading_level"] == 1
    assert by_text["APPENDIX 4 - GLOSSARY"]["section_path"] == (
        "APPENDIX 4 - GLOSSARY"
    )

    assert by_text["Annual Unit Improvement"]["section_path"] == (
        "APPENDIX 4 - GLOSSARY > Annual Unit Improvement"
    )
    
    
    
def test_sop_form_labels_and_table_headers_are_not_headings(tmp_path):
    path = tmp_path / "sop_form_labels.pdf"

    with pymupdf.open() as document:
        document.new_page()
        document.save(path)

    lines = [
        {
            "page": 1,
            "text": "SOP: LUBRICATION INSTRUCTIONS",
            "size": 14.0,
            "bold": True,
            "bbox": (50.0, 30.0, 350.0, 50.0),
            "char_start": 0,
            "char_end": 30,
        },
        {
            "page": 1,
            "text": "IR GUN",
            "size": 7.9,
            "bold": True,
            "bbox": (50.0, 100.0, 120.0, 112.0),
            "char_start": 31,
            "char_end": 37,
        },
        {
            "page": 1,
            "text": "OTHER (SPECIFY)",
            "size": 7.9,
            "bold": True,
            "bbox": (50.0, 120.0, 160.0, 132.0),
            "char_start": 38,
            "char_end": 54,
        },
        {
            "page": 1,
            "text": "LOCATION",
            "size": 11.0,
            "bold": True,
            "bbox": (50.0, 160.0, 140.0, 175.0),
            "char_start": 55,
            "char_end": 63,
        },
        {
            "page": 1,
            "text": "JOB STEPS",
            "size": 11.0,
            "bold": True,
            "bbox": (200.0, 160.0, 300.0, 175.0),
            "char_start": 64,
            "char_end": 73,
        },
    ]

    result = detect_sections(path, lines)
    by_text = {line["text"]: line for line in result}

    assert by_text["IR GUN"]["heading_level"] is None
    assert by_text["OTHER (SPECIFY)"]["heading_level"] is None
    assert by_text["LOCATION"]["heading_level"] is None
    assert by_text["JOB STEPS"]["heading_level"] is None