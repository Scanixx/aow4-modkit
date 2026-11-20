"""Check an SDK source ZIP or wheel for unexpected/private development files.

This is a release hygiene check, not a guarantee that arbitrary secrets can be
detected. It never reads account credentials or files outside supplied archives.
"""
import argparse
import json
from pathlib import PurePosixPath, Path
import re
import zipfile

SOURCE_ROOT_FILES = {"README.md", "NOTICE.md", "CHANGELOG.md", "pyproject.toml",
                     ".gitignore", "LICENSE", "LICENSE.txt", "source-manifest.json"}
SOURCE_DIRECTORIES = {"src", "docs", "examples", "tests", "tools"}
ALLOWED_TOOLS = {"generate_reference.py", "package_source.py", "audit_distribution.py"}
FORBIDDEN_PARTS = {"research", ".git", ".codex", ".agents", "__pycache__", "artifacts", "build", ".venv"}
PRIVATE_MARKERS = (
    re.compile(r"[A-Z]:[\\/](?:Users|SteamLibrary|AOW4 Mods)[\\/]", re.I),
    re.compile(r"/(?:Users|home)/[^/\s]+/"),
    re.compile(r"<(?:send_user_message_question_reply|environment_context|app-context)>"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
)


def audit(path):
    problems, checked = [], []
    wheel = path.suffix == ".whl"
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, "Corrupt ZIP entry"
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            parts = PurePosixPath(name).parts
            if ".." in parts or PurePosixPath(name).is_absolute() or any(p in FORBIDDEN_PARTS for p in parts):
                problems.append({"file": name, "reason": "Unexpected or private directory"})
                continue
            if wheel:
                valid = parts[0] == "aow4modkit" or (parts[0].startswith("aow4modkit-") and parts[0].endswith(".dist-info"))
            else:
                valid = parts[0] == "AoW4ModKit" and len(parts) >= 2
                if valid:
                    relative = parts[1:]
                    valid = (len(relative) == 1 and relative[0] in SOURCE_ROOT_FILES) or (
                        len(relative) > 1 and relative[0] in SOURCE_DIRECTORIES and
                        PurePosixPath(name).suffix in {".py", ".md", ".json"})
                    if valid and relative[0] == "tools":
                        valid = len(relative) == 2 and relative[1] in ALLOWED_TOOLS
            if not valid or PurePosixPath(name).suffix.lower() in {".rpk", ".acp", ".clb", ".png", ".exe", ".dll", ".pe", ".pyc"}:
                problems.append({"file": name, "reason": "Not part of the intended SDK distribution"})
            raw = archive.read(name)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                problems.append({"file": name, "reason": "Unexpected binary payload"})
                continue
            if any(pattern.search(text) for pattern in PRIVATE_MARKERS):
                problems.append({"file": name, "reason": "Private-path, conversation or credential marker"})
            checked.append(name)
    return {"archive": path.name, "checked_files": len(checked), "issues": problems,
            "passed": not problems, "scope": "Allowlist and text marker inspection; manual review remains necessary."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    reports = [audit(path) for path in args.archives]
    print(json.dumps(reports, indent=2))
    raise SystemExit(0 if all(report["passed"] for report in reports) else 1)
