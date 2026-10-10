# Noesis

Noesis is a domain-specific retrieval system for centrifugal pump maintenance
documentation. Development begins with corpus management and equipment-tag
normalization.

## Current status

Phase 0 establishes:
- A document manifest with SHA-256 checksums.
- A corpus fetcher that validates downloaded files.
- Synthetic pump and inspection documents for local development.
- Equipment-tag normalization and automated tests.

The end-to-end retrieval pipeline is not implemented yet.

## Corpus and source limitations

The corpus includes OEM pump documentation, a bearing/vibration guide,
an OSHA lockout/tagout reference, and synthetic documents.

The lubrication SOP source is a DOCX document, while the manifest checksum
describes a locally converted PDF. The fetcher skips this document because
the conversion is not reproducible through the current fetch script.

The SOP is a generic lubrication-instruction template, not a verified,
pump-specific lubrication procedure. Do not use it as evidence for
pump-specific lubrication intervals, schedules, or recommendations.

## Evaluation scope

Lubrication-schedule questions are out of scope until a suitable,
pump-specific source is added and verified. They must not be counted as
answerable evaluation cases.

## Setup and tests

Use Python 3.11 or a compatible version. Activate your virtual environment
and install the project's required dependencies.

Run tests with: `python -m pytest -v`

Check the corpus with: `python fetch_corpus.py`

Synthetic documents are included under `corpus/synthetic/` and are not
downloaded by the fetcher. External documents are subject to source
availability and checksum verification.

## Current limitations

Noesis currently provides corpus management and tag normalization.
Document parsing, retrieval, ranking, grounded answer generation, citation
validation, and evaluation remain future implementation steps.
