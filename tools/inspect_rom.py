"""Read-only identity check and optional explicit-mode token inspection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from frlg.rom import GateError, Image
from frlg.text import read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--kind", choices=("release", "original"), default="release")
    parser.add_argument("--offset", type=lambda s: int(s, 0))
    parser.add_argument("--mode", choices=("jp", "cn"))
    args = parser.parse_args()
    if (args.offset is None) != (args.mode is None):
        parser.error("--offset and --mode must be supplied together")
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    image = Image.load(args.rom, manifest[args.kind + "_sha256"], manifest["size"])
    result = dict(identity="PASS", sha256=image.digest, size=len(image.data))
    if args.offset is not None:
        stream = read(image.data, args.offset, args.mode)
        result["stream"] = dict(status=stream.status, end=stream.end,
                               tokens=[dict(offset=o, kind=k, hex=b.hex()) for o, k, b in stream.tokens])
        if stream.status != "OK":
            raise GateError(f"stream rejected: {stream.status}")
    image.unchanged()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (GateError, OSError, ValueError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
