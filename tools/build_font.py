"""Compile caller-owned glyph JSON to pages/charmap; never reads or writes a ROM."""
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


def run(source: Path, output_dir: Path | None = None):
    before = sha(source.read_bytes())
    artifacts, report = build_font(load_recipe(source))
    if sha(source.read_bytes()) != before:
        raise GateError("glyph input changed during run")
    report.update(input_sha256=before, written=False)
    if output_dir is not None:
        # Never merge into an old directory or overwrite an existing artifact.
        output_dir.mkdir(exist_ok=False)
        for name, data in artifacts.items():
            target = output_dir / name
            with target.open("xb") as handle:
                handle.write(data)
            if sha(target.read_bytes()) != report["artifacts"][name]["sha256"]:
                raise GateError("artifact readback mismatch; output is not validated")
        if sha(source.read_bytes()) != before:
            raise GateError("glyph input changed during write")
        report["written"] = True
        with (output_dir / "manifest.json").open("x", encoding="utf8") as handle:
            json.dump(report, handle, ensure_ascii=True, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyphs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, help="new directory only; omit for dry run")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.glyphs, args.output_dir), indent=2))
    except (GateError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
