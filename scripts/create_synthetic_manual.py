
import hashlib
import textwrap
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "corpus" / "synthetic"
    / "Synthetic_Centrifugal_Pump_Manual.pdf"
)

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 54
BODY_SIZE = 10
BODY_LINE_HEIGHT = 15

pdf = None
page = None
y = 0
bookmarks = []


def new_page(title):
    global page, y

    page = pdf.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text(
        (LEFT, 45),
        "SYNTHETIC CENTRIFUGAL PUMP MANUAL",
        fontsize=9,
        fontname="helv",
        color=(0.35, 0.35, 0.35),
    )
    page.draw_line(
        (LEFT, 56), (PAGE_WIDTH - LEFT, 56),
        color=(0.65, 0.65, 0.65),
    )
    page.insert_text(
        (LEFT, 88), title, fontsize=17, fontname="hebo"
    )
    y = 115
    return len(pdf) - 1


def heading(number, title, level=1):
    global y

    sizes = {1: 14, 2: 12, 3: 11}
    font = "hebo"
    size = sizes[level]
    text = f"{number} {title}"

    page.insert_text(
        (LEFT, y), text, fontsize=size, fontname=font
    )
    bookmarks.append(
        [level, text, len(pdf)]
    )
    y += size + 13


def paragraph(text, width=82):
    global y

    # Preserve intentional physical line breaks so that the
    # fixture can test extraction of line-break hyphenation.
    for physical_line in text.strip().splitlines():
        lines = textwrap.wrap(
            physical_line.strip(),
            width=width,
            replace_whitespace=True,
            drop_whitespace=True,
        ) or [""]

        for line in lines:
            if y > 755:
                raise ValueError(
                    f"Content overflows page at: {line}"
                )

            page.insert_text(
                (LEFT, y),
                line,
                fontsize=BODY_SIZE,
                fontname="helv",
            )
            y += BODY_LINE_HEIGHT

    y += 7


def warning(text):
    global y

    page.insert_text(
        (LEFT, y),
        "WARNING",
        fontsize=12,
        fontname="hebo",
        color=(0.65, 0.05, 0.05),
    )
    y += 19

    # Bold warning body makes the warning block visually distinct.
    for line in textwrap.wrap(text, width=82):
        page.insert_text(
            (LEFT, y),
            line,
            fontsize=10,
            fontname="hebo",
        )
        y += BODY_LINE_HEIGHT

    y += 10


def troubleshooting_table():
    global y

    caption = "Table 5.1 — Illustrative troubleshooting guide"
    page.insert_text(
        (LEFT, y),
        caption,
        fontsize=10,
        fontname="hebo",
    )
    y += 12

    headers = ["Observed condition", "Possible area", "Next step"]
    rows = [
        [
            "Low discharge flow",
            "Supply or suction",
            "Check approved procedure",
        ],
        [
            "Elevated vibration",
            "Alignment or bearing",
            "Compare with baseline",
        ],
        [
            "Seal-area leakage",
            "Seal or connections",
            "Follow site procedure",
        ],
    ]

    x_positions = [LEFT, 218, 352, PAGE_WIDTH - LEFT]
    row_height = 39
    all_rows = [headers] + rows

    for row_index, row in enumerate(all_rows):
        for col_index, value in enumerate(row):
            x0 = x_positions[col_index]
            x1 = x_positions[col_index + 1]
            y0 = y
            y1 = y + row_height

            page.draw_rect(
                pymupdf.Rect(x0, y0, x1, y1),
                color=(0.2, 0.2, 0.2),
                width=0.8,
            )

            font = "hebo" if row_index == 0 else "helv"
            size = 8.5

            page.insert_textbox(
                pymupdf.Rect(
                    x0 + 4, y0 + 5, x1 - 4, y1 - 3
                ),
                value,
                fontsize=size,
                fontname=font,
                align=0,
            )

        y += row_height

    y += 15


def build_manual():
    global pdf, y

    pdf = pymupdf.open()

    # Page 1
    new_page("1. Purpose and limitations")
    heading("1", "Purpose and limitations", 1)
    heading("1.1", "Scope", 2)
    paragraph(
        "This fictional manual exists to test the Noesis document "
        "ingestion and retrieval pipeline. The pump, model, and "
        "scenarios are invented for software testing."
    )
    heading("1.1.1", "Synthetic status", 3)
    paragraph(
        "This is NOT an OEM manual. No real equipment specifications, "
        "measured results, or validated maintenance limits are provided. "
        "See Section 2, Safety, for the general safety context."
    )
    heading("1.2", "Use limitations", 2)
    paragraph(
        "Never use this document to select, install, operate, repair, "
        "or maintain real equipment. Consult the actual manufacturer's "
        "manual and approved site procedures."
    )

    # Page 2
    new_page("2. Safety")
    heading("2", "Safety", 1)
    warning(
        "This synthetic document is not an authorized safety procedure. "
        "Before maintenance, follow applicable site rules, equipment "
        "instructions, energy-isolation requirements, and verification "
        "steps. Only qualified and authorized personnel may perform "
        "assigned work."
    )
    heading("2.1", "General safety", 2)
    paragraph(
        "Identify hazards before starting work. Do not bypass guards, "
        "interlocks, or approved procedures. See Section 2.1.1 for "
        "the energy-isolation topic."
    )
    heading("2.1.1", "Energy isolation", 3)
    paragraph(
        "Follow the site's approved lockout/tagout process and verify "
        "the required safe state before work. This text is an overview, "
        "not a substitute for the applicable procedure."
    )

    # Page 3
    new_page("3. Fictional equipment record")
    heading("3", "Fictional equipment record", 1)
    heading("3.1", "Equipment identification", 2)
    paragraph(
        "Equipment tag: P-101A\n"
        "Alternate tag display: P 101 A\n"
        "Another tag display: p101a\n"
        "Description: Fictional centrifugal water-transfer pump\n"
        "Fictional model: SYN-100\n"
        "Inspection or test data: None collected"
    )
    heading("3.1.1", "Tag interpretation", 3)
    paragraph(
        "The three tag strings above are surface forms intended for "
        "normalization tests. A canonical tag must not accidentally "
        "merge P101 with P101A. API 610 is a standard designation, "
        "not an equipment tag in this fixture."
    )
    heading("3.2", "Basic components", 2)
    paragraph(
        "A centrifugal pump may include an impeller, casing, shaft, "
        "bearings, shaft seal, suction connection, and discharge "
        "connection. Actual designs vary by manufacturer and model."
    )

    # Page 4
    new_page("4. Maintenance and condition observations")
    heading("4", "Maintenance and condition observations", 1)
    heading("4.1", "Bearing observations", 2)
    paragraph(
        "Record visible condition, unusual noise, lubrication "
        "observations, and vibration relative to an established "
        "baseline. Consult the equipment-specific limits."
    )
    heading("4.1.1", "Vibration observations", 3)
    paragraph(
        "A change in vibration may have several possible causes. "
        "Misalign-\n"
        "ment, imbalance, looseness, bearing damage, and hydraulic "
        "conditions are illustrative topics only."
    )
    heading("4.2", "Lubrication observations", 2)
    paragraph(
        "Record the lubricant identity and actual observed condition "
        "when those data are available. Do not infer a missing "
        "measurement or assume that one lubricant fits every pump."
    )

    # Page 5
    new_page("5. Troubleshooting")
    heading("5", "Troubleshooting", 1)
    heading("5.1", "Low discharge flow", 2)
    paragraph(
        "Possible investigation areas include liquid supply, suction "
        "restriction, air ingress, valve position, rotation, and "
        "operating conditions. See Section 2, Safety, before work."
    )
    heading("5.2", "Elevated vibration", 2)
    paragraph(
        "Possible contributors include misalignment, imbalance, "
        "looseness, bearing damage, or hydraulic conditions. Compare "
        "measurements with valid equipment-specific baselines."
    )
    troubleshooting_table()

    # Page 6
    new_page("6. Inspection records")
    heading("6", "Inspection records", 1)
    heading("6.1", "Recording observations", 2)
    paragraph(
        "Record the equipment tag, date, observation, measurement, "
        "units, and source of the measurement when available. Keep "
        "observations distinct from interpretations and recommendations."
    )
    heading("6.1.1", "Missing information", 3)
    paragraph(
        "If a value is unavailable, mark it as unavailable. Never "
        "invent missing measurements, thresholds, or inspection results."
    )
    heading("6.2", "Illustrative inspection notes", 2)
    paragraph(
        "Equipment: P-101A\n"
        "Observed condition: Not supplied\n"
        "Measured vibration: Not supplied\n"
        "Assessment: Cannot be determined from this fixture"
    )

    # Page 7
    new_page("7. Document control")
    heading("7", "Document control", 1)
    heading("7.1", "Document identity", 2)
    paragraph(
        "Document ID: SYN-PUMP-MAN-001\n"
        "Status: Fictional training document — NOT AN OEM MANUAL\n"
        "Fictional model: SYN-100"
    )
    heading("7.1.1", "Permitted use", 3)
    paragraph(
        "This fixture tests PDF extraction, heading detection, table "
        "parsing, warning isolation, equipment-tag normalization, "
        "and source-grounded retrieval. It does not validate real "
        "maintenance procedures or equipment limits."
    )
    heading("7.2", "Cross-reference", 2)
    paragraph(
        "Sections 1, 3, and 5 refer readers to Section 2, Safety. "
        "The reference is intentionally repeated to test section-aware "
        "chunking and retrieval."
    )

    # PDF bookmarks use 1-based page numbers.
    pdf.set_toc(bookmarks)
    pdf.set_metadata(
        {
            "title": "Synthetic Centrifugal Pump Manual",
            "author": "Noesis test fixture",
            "subject": "Fictional document for ingestion testing",
            "keywords": "synthetic, pump, safety, testing",
        }
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(OUTPUT, garbage=4, deflate=True)
    pdf.close()


def main():
    build_manual()
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()

    print(f"Created: {OUTPUT.relative_to(ROOT)}")
    print("Pages: 7")
    print("Bookmarks: 7+")
    print("Table: bordered troubleshooting table")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
