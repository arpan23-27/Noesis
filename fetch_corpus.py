
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CORPUS_DIR = ROOT / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

# The source is a DOCX, but the manifest hash belongs to its converted PDF.
CONVERTED_SOURCE_FILES = {"lubrication_sop.pdf"}


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    request = Request(
        url,
        headers={"User-Agent": "Noesis-Corpus-Fetcher/1.0"},
    )

    with urlopen(request, timeout=30) as response:
        content = response.read()

    if not content:
        raise ValueError(f"Downloaded file is empty: {url}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def process_document(document: dict, corpus_dir: Path) -> None:
    filename = document["filename"]

    if document.get("synthetic", False):
        print(f"SKIP synthetic document: {filename}")
        return

    if filename in CONVERTED_SOURCE_FILES:
        print(
            f"SKIP {filename}: source is a DOCX, "
            "but the manifest hash belongs to the converted PDF."
        )
        return

    url = document.get("url")
    expected_hash = document.get("sha256")

    if not isinstance(url, str) or not url.startswith(
        ("https://", "http://")
    ):
        raise ValueError(f"Invalid download URL for {filename}: {url!r}")

    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError(f"Invalid SHA-256 in manifest for {filename}")

    destination = corpus_dir / filename
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file():
        if calculate_sha256(destination) == expected_hash:
            print(f"OK: {filename} matches the manifest")
            return

    print(f"Downloading: {filename}")
    download_file(url, destination)

    actual_hash = calculate_sha256(destination)

    if actual_hash != expected_hash:
        destination.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch for {filename}; "
            "downloaded file removed."
        )

    print(f"VERIFIED: {filename}")


def main() -> None:
    with MANIFEST_PATH.open("r", encoding="utf-8-sig") as file:
        documents = json.load(file)

    for document in documents:
        process_document(document, CORPUS_DIR)


if __name__ == "__main__":
    main()
