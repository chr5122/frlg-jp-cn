"""Create a blank, caller-owned glyph input for the first-line experiment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from frlg.font_pack import build_font
from frlg.original_probe import NATIVE_PUNCTUATION, text_lines
from frlg.rom import GateError


def template(line: str, source: str) -> dict:
    lines = text_lines(line)
    if not isinstance(source, str) or not source.strip():
        raise GateError("describe the source and permission for your own glyph input")
    # At most 28 characters; IDs 0x0100..0x011B contain no FF byte.
    characters = list(dict.fromkeys(c for c in "".join(lines) if c not in NATIVE_PUNCTUATION))
    if not characters:
        raise GateError("the experiment requires at least one private character")
    document = {"schema": 1, "source": source, "glyphs": [
        {"unicode": char, "glyph_id": f"0x{0x100 + index:04X}",
         "pixels": [[0] * 16 for _ in range(16)]}
        for index, char in enumerate(characters)
    ]}
    # Reuse the actual packer's character validation, including native glyphs.
    build_font(document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="one or two lines, at most 14 characters each")
    parser.add_argument("--source", required=True, help="describe the intended glyph source and permission")
    parser.add_argument("--output", type=Path, required=True, help="new JSON file only")
    args = parser.parse_args()
    try:
        document = template(args.text, args.source)
        encoded = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf8")
        with args.output.open("xb") as handle:
            handle.write(encoded)
        if args.output.read_bytes() != encoded:
            raise GateError("template readback mismatch")
        print("Blank template created. Draw your own pixels before building the experiment.")
        return 0
    except (GateError, OSError, ValueError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
