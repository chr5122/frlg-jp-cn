"""Pinned BUILD0107 -> BUILD0108 range fix. Dry-run unless --output is given.

No source strings, font, save records or new instructions are written.
This is not a clean-Japanese-ROM to complete-Chinese-ROM build script.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from frlg.rom import GateError, Image, sha, span, verify_changes

PARENT_SHA = "392d177d3ed996aa74c7906be1a4ae7da5417a714419c7ad1309400d02eba85f"
PRODUCT_SHA = "6c607d48d4410a54370590b834198bdfd1bc171db46dfe273e6942b0d047d944"
HELPER_SHA = "7b55f0c9e161cd8012104ba574c745e666e3cc640bb0839929cd03bac3b8843b"


def patch(parent: bytes) -> tuple[bytes, dict]:
    if len(parent) != 0x1000000 or sha(parent) != PARENT_SHA:
        raise GateError("requires the exact BUILD0107 parent")
    if sha(span(parent, 0xE3BB00, 0x288)) != HELPER_SHA:
        raise GateError("existing helper identity mismatch")
    if struct.unpack_from("<III", parent, 0xE3BCE8) != (0x08203CB8, 0x082045CA, 387):
        raise GateError("existing literal preimage mismatch")
    product = bytearray(parent)
    writes = []
    for offset, value in ((0xE3BCEC, 0x08204660), (0xE3BCF0, 412)):
        after = struct.pack("<I", value)
        product[offset:offset + 4] = after
        writes.append(dict(offset=offset, before_hex=parent[offset:offset + 4].hex(),
                           after_hex=after.hex(), purpose="display_literal"))
    result = bytes(product)
    report = verify_changes(parent, result, writes, [])
    if sha(result) != PRODUCT_SHA or report["changed_bytes"] != 3:
        raise GateError("product identity or delta mismatch")
    return result, dict(**report, sha256=PRODUCT_SHA, writes=writes,
                        new_instructions=0, new_allocations=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    image = Image.load(args.parent, PARENT_SHA, 0x1000000)
    result, report = patch(image.data)
    image.unchanged()
    if args.output:
        if args.output.resolve() == image.path:
            raise GateError("refusing to overwrite the input")
        with args.output.open("xb") as target:
            target.write(result)
        if sha(args.output.read_bytes()) != PRODUCT_SHA:
            raise GateError("output verification failed")
    image.unchanged()
    report["output_written"] = args.output is not None
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (GateError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
