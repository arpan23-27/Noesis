
import hashlib

import pytest

import fetch_corpus


def make_document(content: bytes, filename: str = "sample.pdf") -> dict:
    return {
        "filename": filename,
        "type": "test_document",
        "url": "https://example.com/sample.pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
        "synthetic": False,
    }


def test_downloads_missing_file_and_verifies_hash(tmp_path, monkeypatch):
    content = b"synthetic test PDF bytes"
    document = make_document(content, "nested/sample.pdf")
    destination = tmp_path / "nested" / "sample.pdf"

    def fake_download(url, path):
        path.write_bytes(content)

    monkeypatch.setattr(fetch_corpus, "download_file", fake_download)

    fetch_corpus.process_document(document, tmp_path)

    assert destination.is_file()
    assert fetch_corpus.calculate_sha256(destination) == document["sha256"]


def test_skips_existing_file_with_matching_hash(tmp_path, monkeypatch):
    content = b"already verified"
    document = make_document(content)
    destination = tmp_path / document["filename"]
    destination.write_bytes(content)

    def unexpected_download(url, path):
        pytest.fail("A matching file should not be downloaded again")

    monkeypatch.setattr(fetch_corpus, "download_file", unexpected_download)

    fetch_corpus.process_document(document, tmp_path)

    assert destination.read_bytes() == content


def test_deletes_downloaded_file_when_hash_mismatches(tmp_path, monkeypatch):
    expected = b"expected content"
    document = make_document(expected)
    destination = tmp_path / document["filename"]

    def fake_download(url, path):
        path.write_bytes(b"incorrect content")

    monkeypatch.setattr(fetch_corpus, "download_file", fake_download)

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        fetch_corpus.process_document(document, tmp_path)

    assert not destination.exists()


def test_skips_synthetic_document(tmp_path, monkeypatch):
    document = {
        "filename": "synthetic/manual.pdf",
        "url": None,
        "sha256": "not-used",
        "synthetic": True,
    }

    def unexpected_download(url, path):
        pytest.fail("Synthetic documents must not be downloaded")

    monkeypatch.setattr(fetch_corpus, "download_file", unexpected_download)

    fetch_corpus.process_document(document, tmp_path)

    assert not (tmp_path / document["filename"]).exists()


def test_rejects_invalid_url(tmp_path):
    document = make_document(b"content")
    document["url"] = None

    with pytest.raises(ValueError, match="Invalid download URL"):
        fetch_corpus.process_document(document, tmp_path)


def test_skips_converted_lubrication_document(tmp_path, monkeypatch):
    document = make_document(b"converted PDF")
    document["filename"] = "lubrication_sop.pdf"

    def unexpected_download(url, path):
        pytest.fail("Converted source should be skipped")

    monkeypatch.setattr(fetch_corpus, "download_file", unexpected_download)

    fetch_corpus.process_document(document, tmp_path)

    assert not (tmp_path / document["filename"]).exists()
