
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CORPUS_DIR = ROOT / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


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

    destination.write_bytes(content)


def main() -> None:
    with MANIFEST_PATH.open("r", encoding="utf-8-sig") as file:
        documents = json.load(file)

    for document in documents:
        if document.get("synthetic", False):
            print(f"SKIP synthetic document: {document['filename']}")
            continue

        filename = document["filename"]
        expected_hash = document["sha256"]
        url = document["url"]
        destination = CORPUS_DIR / filename

        # The lubrication URL is a DOCX, but its manifest hash
        # currently belongs to the converted PDF.
        if filename == "lubrication_sop.pdf":
            print(
                "SKIP lubrication_sop.pdf: its source is DOCX "
                "but the recorded hash belongs to the converted PDF."
            )
            continue

        if destination.exists():
            actual_hash = calculate_sha256(destination)

            if actual_hash == expected_hash:
                print(f"OK: {filename} matches the manifest")
                continue

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


if __name__ == "__main__":
    main()
