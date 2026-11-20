"""Package authored SDK source, excluding game data and generated artifacts."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0a4"
SOURCE_DIRECTORIES = ("src", "docs", "examples", "tests", "tools")
ROOT_FILES = ("README.md", "NOTICE.md", "CHANGELOG.md", "pyproject.toml", ".gitignore", "LICENSE")
EXCLUDED_PARTS = {"__pycache__", "artifacts", "build", "dist", ".git", ".venv"}
SOURCE_SUFFIXES = {".py", ".md", ".json"}


def main():
    paths = [ROOT / name for name in ROOT_FILES]
    for directory in SOURCE_DIRECTORIES:
        for path in (ROOT / directory).rglob("*"):
            parts = path.relative_to(ROOT).parts
            if path.is_file() and not any(p in EXCLUDED_PARTS or p.endswith(".egg-info") for p in parts) and path.suffix in SOURCE_SUFFIXES:
                paths.append(path)
    files = {"AoW4ModKit/" + p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
    manifest = {"name": "AoW4 ModKit", "version": VERSION,
                "license": "MIT",
                "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
                "game_binaries_included": False, "published": False}
    files["AoW4ModKit/source-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    destination = ROOT / "artifacts" / f"aow4modkit-{VERSION}-source.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, raw, compresslevel=9)
    with zipfile.ZipFile(destination) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError("Source ZIP CRC check failed")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(zipped.read(name)).hexdigest() != digest:
                raise RuntimeError(f"Source ZIP hash mismatch: {name}")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(digest + "  " + destination.name + "\n", encoding="ascii")
    print(json.dumps({"source_archive": str(destination), "source_files": len(paths), "sha256": digest}))


if __name__ == "__main__":
    main()
