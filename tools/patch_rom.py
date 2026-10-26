"""Apply a reviewed recipe directly to an exact Japanese original; dry-run by default."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from frlg.patching import PROFILES, apply_recipe
from frlg.rom import GateError, Image, sha


def load_recipe(path: Path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise GateError(f"duplicate JSON field: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf8"), object_pairs_hook=unique_pairs)


def run(original: Path, recipe_path: Path, output: Path | None = None):
    recipe = load_recipe(recipe_path)
    if not isinstance(recipe, dict) or not isinstance(recipe.get("game"), str):
        raise GateError("recipe must name a game profile")
    profile = PROFILES.get(recipe["game"])
    if profile is None:
        raise GateError("only Japanese BPRJ/BPGJ Rev0 originals are supported")
    if output is not None:
        if output.resolve() in (original.resolve(), recipe_path.resolve()):
            raise GateError("output must not replace an input")
        if output.exists() or output.is_symlink():
            raise GateError("output already exists; choose a new filename")
    image = Image.load(original, profile["sha256"], profile["size"])
    product, report = apply_recipe(image.data, recipe, expected_sha256=image.digest,
                                   size=profile["size"])
    image.unchanged()
    report["written"] = False
    if output is not None:
        with output.open("xb") as handle:
            handle.write(product)
        if sha(output.read_bytes()) != report["output_sha256"]:
            raise GateError("output readback mismatch; output is not validated")
        image.unchanged()
        report["written"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="new file only; omit for in-memory validation")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.original, args.recipe, args.output), indent=2))
    except (GateError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
