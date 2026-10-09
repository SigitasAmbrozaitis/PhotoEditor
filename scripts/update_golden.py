"""Regenerate the committed synthetic golden images in tests/golden/ (run after an intended engine change).

    uv run python scripts/update_golden.py

This is repository maintenance, like editing code: it writes into tests/, not into the tool's data folders.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from photoedit.core.golden import render_synthetic, synthetic_cases

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden"


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    for stem, profile, edit in synthetic_cases():
        Image.fromarray(render_synthetic(profile, edit)).save(GOLDEN_DIR / f"{stem}.png")
        print(f"wrote tests/golden/{stem}.png")


if __name__ == "__main__":
    main()
