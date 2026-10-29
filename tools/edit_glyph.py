"""Preview or replace one caller-owned glyph using a 12 by 12 text grid."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frlg.font_pack import build_font
from frlg.rom import GateError, sha
from patch_rom import load_recipe


def find_glyph(document: dict, character: str) -> dict:
    build_font(document)
    matches = [glyph for glyph in document["glyphs"] if glyph["unicode"] == character]
    if len(matches) != 1:
        raise GateError("character is not allocated in this glyph document")
    return matches[0]


def parse_grid(text: str) -> list[list[int]]:
    rows = text.splitlines()
    if len(rows) != 12 or any(len(row) != 12 or any(c not in ".12" for c in row) for row in rows):
        raise GateError("grid must have exactly 12 lines of 12 characters, using only . 1 2")
    return [[0 if c == "." else int(c) for c in row] for row in rows]


def render_grid(glyph: dict) -> str:
    symbols = ".12"
    return "\n".join("".join(symbols[pixel] for pixel in row[:12])
                     for row in glyph["pixels"][:12]) + "\n"


def run(source: Path, character: str, grid: Path | None = None, output: Path | None = None) -> str:
    if (grid is None) != (output is None):
        raise GateError("--grid and --output must be supplied together")
    if output is not None and (output.exists() or output.is_symlink() or
                               output.resolve() in (source.resolve(), grid.resolve())):
        raise GateError("output must be a new file, not an input")
    source_sha = sha(source.read_bytes())
    document = load_recipe(source)
    glyph = find_glyph(document, character)
    if grid is None:
        if sha(source.read_bytes()) != source_sha:
            raise GateError("glyph input changed during preview")
        return render_grid(glyph)
    grid_bytes = grid.read_bytes()
    rows = parse_grid(grid_bytes.decode("utf8"))
    glyph["pixels"] = [row + [0] * 4 for row in rows] + [[0] * 16 for _ in range(4)]
    build_font(document)
    if sha(source.read_bytes()) != source_sha or grid.read_bytes() != grid_bytes:
        raise GateError("input changed during editing")
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf8")
    with output.open("xb") as handle:
        handle.write(encoded)
    if output.read_bytes() != encoded:
        raise GateError("output readback mismatch; output is not validated")
    if sha(source.read_bytes()) != source_sha or grid.read_bytes() != grid_bytes:
        raise GateError("input changed during write; output is not validated")
    return render_grid(glyph)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyphs", type=Path, required=True)
    parser.add_argument("--char", required=True, help="one allocated character")
    parser.add_argument("--grid", type=Path, help="12-line UTF-8 grid using . 1 2")
    parser.add_argument("--output", type=Path, help="new glyph JSON file; requires --grid")
    args = parser.parse_args()
    try:
        print(run(args.glyphs, args.char, args.grid, args.output), end="")
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
