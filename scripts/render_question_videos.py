#!/usr/bin/env python3

"""Render generated medical question compositions without overwriting prior videos."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "generated" / "compositions"
RENDER_ROOT = ROOT / "renders"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="1-1")
    parser.add_argument("--quality", choices=("draft", "standard", "high"), default="standard")
    parser.add_argument("--suffix", default="final-checked")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--variant", default="v1")
    parser.add_argument("--file-prefix", default="question")
    parser.add_argument("--background", choices=("white", "green"), default="white")
    args = parser.parse_args()
    start, end = (int(value) for value in args.questions.split("-", 1))

    for number in range(start, end + 1):
        source = args.source_dir.resolve() / f"{args.file_prefix}-q{number:02d}-{args.background}-{args.variant}.html"
        output = RENDER_ROOT / f"{args.file_prefix}-q{number:02d}-{args.background}-{args.variant}-{args.suffix}.mp4"
        if not source.exists():
            raise FileNotFoundError(f"Missing composition: {source}")
        if output.exists():
            print(f"q{number:02d}: reusing {output.name}", flush=True)
            continue
        print(f"q{number:02d}: rendering {args.quality}", flush=True)
        subprocess.run(
            [
                "npx", "hyperframes", "render", ".", "-c",
                str(source.relative_to(ROOT)), "--output", str(output.relative_to(ROOT)),
                "--quality", args.quality, "--workers", "4", "--strict",
                "--skill", "hyperframes",
            ],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    main()
