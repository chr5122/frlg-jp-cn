"""Build the experimental first-Oak-line display from an exact Japanese original."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frlg.original_probe import build
from frlg.patching import PROFILES
from frlg.rom import GateError, Image, sha
from patch_rom import load_recipe


def run(original: Path, game: str, glyphs: Path, line: str, output: Path | None = None,
        arm_prefix="arm-none-eabi-"):
    profile = PROFILES[game]
    if output is not None and (output.exists() or output.is_symlink() or
            output.resolve() in (original.resolve(), glyphs.resolve())):
        raise GateError("output must be a new file, not an input")
    image = Image.load(original, profile["sha256"], profile["size"])
    glyph_sha = sha(glyphs.read_bytes())
    product, report = build(image.data, game, load_recipe(glyphs), line, arm_prefix=arm_prefix)
    image.unchanged()
    if sha(glyphs.read_bytes()) != glyph_sha:
        raise GateError("glyph input changed")
    report.update(glyph_input_sha256=glyph_sha, written=False)
    if output is not None:
        with output.open("xb") as handle:
            handle.write(product)
        if sha(output.read_bytes()) != report["output_sha256"]:
            raise GateError("output readback mismatch; output is not validated")
        image.unchanged()
        if sha(glyphs.read_bytes()) != glyph_sha:
            raise GateError("glyph input changed during write")
        report["written"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--game", choices=tuple(PROFILES), required=True)
    parser.add_argument("--glyphs", type=Path, required=True)
    parser.add_argument("--text", required=True, help="up to two pages separated by form feed, at most 28 characters total")
    parser.add_argument("--output", type=Path, help="new file only; default is in-memory validation")
    parser.add_argument("--arm-prefix", default="arm-none-eabi-")
    args = parser.parse_args()
    try:
        report = run(args.original, args.game, args.glyphs, args.text, args.output, args.arm_prefix)
        print(json.dumps(report, indent=2))
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
