"""Generate the function reference from the installed package or source checkout."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aow4modkit.cli import function_reference

if __name__ == "__main__":
    destination = ROOT / "docs/functions.md"
    destination.write_text(function_reference() + "\n", encoding="utf-8")
    print(destination)
