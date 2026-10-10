
import hashlib
import textwrap
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "corpus" / "synthetic" / "Synthetic_Centrifugal_Pump_Manual.pdf"

PAGES = [
    (
        "SYNTHETIC CENTRIFUGAL PUMP MANUAL",
        """
DOCUMENT ID: SYN-PUMP-MAN-001
STATUS: FICTIONAL TRAINING DOCUMENT — NOT AN OEM MANUAL

1. PURPOSE AND LIMITATIONS

This document exists only to test the Noesis document retrieval pipeline.
The pump, model, and scenarios are fictional. No real equipment specifications
or test measurements are represented.

Do not use this document to select, install, operate, repair, or maintain
real equipment. Consult the actual manufacturer's manual and approved
site procedures before taking action.

2. FICTIONAL EQUIPMENT RECORD

Equipment tag: P-101
Description: Centrifugal water-transfer pump
Fictional model: SYN-100
Service: Water transfer
Inspection or test data: None collected

3. BASIC COMPONENTS

A typical centrifugal pump may include an impeller, casing, shaft, bearings,
shaft seal, suction connection, and discharge connection. Actual designs
and component arrangements vary by manufacturer and model.

4. GENERAL INSPECTION TOPICS

An inspection may consider visible leakage, unusual noise, vibration relative
to an established baseline, bearing condition, mounting, and connections.
Record actual observations and measured values separately. Never invent
missing measurements.
""",
    ),
    (
        "SYNTHETIC MANUAL — TROUBLESHOOTING",
        """
5. ILLUSTRATIVE TROUBLESHOOTING CASES

CASE A — NO OR LOW DISCHARGE FLOW

Possible areas to investigate include liquid supply, suction restriction,
air ingress, valve position, rotation, and operating conditions. These are
general examples, not a diagnosis of a particular pump.

CASE B — ELEVATED VIBRATION

Possible contributors include misalignment, imbalance, looseness, bearing
damage, or hydraulic operating conditions. Compare measurements with
equipment-specific limits and historical baselines.

CASE C — SEAL-AREA LEAKAGE

Document the location and observed condition. Use the actual manufacturer's
allowable leakage criteria and approved site procedure to determine action.

6. SAFETY

Do not use this fictional document as a safety procedure. Before work,
follow applicable site requirements and equipment-specific energy isolation,
lockout/tagout, and verification steps. Only qualified and authorized
personnel should perform assigned work.

7. DOCUMENT CONTROL

This document is synthetic and intended only for software testing and
educational demonstrations. Its examples are not verified specifications,
fault findings, performance limits, or maintenance instructions.

END OF SYNTHETIC DOCUMENT
""",
    ),
]


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    pdf = pymupdf.open()

    for title, body in PAGES:
        page = pdf.new_page(width=595, height=842)
        page.insert_text((54, 58), title, fontsize=15, fontname="hebo")
        y = 92

        for paragraph in body.strip().split("\n\n"):
            for line in textwrap.wrap(paragraph.strip(), width=78):
                if y > 790:
                    raise ValueError(f"Content overflows page: {title}")
                page.insert_text((54, y), line, fontsize=10, fontname="helv")
                y += 14
            y += 10

    pdf.save(OUTPUT)
    pdf.close()

    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(f"Created: {OUTPUT.relative_to(ROOT)}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
