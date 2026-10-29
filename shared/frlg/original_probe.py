"""Scoped fresh-game first-Oak-line probe from exact Japanese originals.

Not the current translation build and not a global F7/width/placeholder patch.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .encode import encode
from .font_pack import build_font
from .patching import PROFILES
from .rom import BASE, GateError, sha, span, uint, verify_changes

ROOT = Path(__file__).resolve().parents[2]
POOL, POOL_END = 0xB00000, 0xB40000
CODE, CONFIG, TABLE, TEXT, FONT = 0xB00010, 0xB00400, 0xB00440, 0xB00800, 0xB04000
HOOK = 0x5814
HOOK_BEFORE = bytes.fromhex("181cf838072800d9")
# Only these native glyphs are admitted for this specific fixed-width window.
NATIVE_PUNCTUATION = frozenset("！？。")


def text_lines(text: str) -> list[str]:
    if not isinstance(text, str):
        raise GateError("probe text must be a string")
    lines = text.split("\n")
    if not 1 <= len(lines) <= 2 or any(not 1 <= len(line) <= 14 for line in lines):
        raise GateError("probe requires one or two nonempty lines of at most 14 characters each")
    widths = [sum(16 if c in NATIVE_PUNCTUATION else 12 for c in line) for line in lines]
    if any(width > 168 for width in widths):
        raise GateError("probe line exceeds the conservative 168px width budget")
    return lines


ADAPTERS = {
    "firered-jp-rev0": dict(slot=0x130104, original_text=0x081AA211,
        consumer_start=0x1300CC, consumer_end=0x130124,
        consumer_sha256="bdd136c70ae1becd47167886cd571de08c0bc1ca287711f33abbee9d35758cd1",
        tile_sha256="e7d3346f7da4f6a6b11df4f51dd546a0a493973d0aca297da5cb3e564ee99474"),
    "leafgreen-jp-rev0": dict(slot=0x1300DC, original_text=0x081AA1ED,
        consumer_start=0x1300A4, consumer_end=0x1300FC,
        consumer_sha256="ddc422a484df515676dc950b45604b304ccec0efdf6498ee9e6d4655c9cc19ed",
        tile_sha256="f7c73175c69d1e44ead69ac344a55b42b9a71044946df807f967d3863ae5132c"),
}
PROTECTED = [dict(start=0, end=0xC0, name="ROM header"),
             dict(start=0x6E000, end=0x92000, name="native save/flash code"),
             dict(start=0x1CEDD0, end=0x1F1118, name="native JP fonts and widths"),
             dict(start=0x1F1344, end=0x1F1348, name="native save slot1"),
             dict(start=POOL, end=CODE, name="new pool leading guard")]


def compile_code(length: int, prefix: str = "arm-none-eabi-"):
    definitions = dict(PROBE_LENGTH=length, PROBE_BUFFER=0x02021C88,
        PROBE_TEXT=BASE+TEXT, PROBE_CONFIG=BASE+CONFIG,
        PROBE_COPY_GLYPH=0x08005B2B, PROBE_NATIVE_GLYPH=0x08005ACD,
        PROBE_NATIVE_SWITCH=0x0800581F)
    sources = [ROOT / "shared/patches" / name for name in ("cn_original_probe.s", "cn_glyph.s")]
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        objects = []
        for index, source in enumerate(sources):
            obj = tmp / f"{index}.o"
            flags = [item for key, value in definitions.items() for item in ("--defsym", f"{key}={value}")]
            subprocess.run([prefix+"as", "-mcpu=arm7tdmi", "-mthumb", *flags,
                            str(source), "-o", str(obj)], check=True, capture_output=True)
            objects.append(str(obj))
        elf, binary = tmp / "probe.elf", tmp / "probe.bin"
        subprocess.run([prefix+"ld", f"-Ttext={BASE+CODE:#x}", "-e", "cn_probe_prefix",
                        *objects, "-o", str(elf)], check=True, capture_output=True)
        subprocess.run([prefix+"objcopy", "-O", "binary", str(elf), str(binary)],
                       check=True, capture_output=True)
        code = binary.read_bytes()
    if not code or len(code) > CONFIG-CODE:
        raise GateError("probe code exceeds its reserved code window")
    return code, {str(source.relative_to(ROOT)): sha(source.read_bytes()) for source in sources}


def build(parent: bytes, game: str, glyph_document: dict, line: str, *, arm_prefix="arm-none-eabi-"):
    profile = PROFILES.get(game)
    if not profile or len(parent) != profile["size"] or sha(parent) != profile["sha256"]:
        raise GateError("requires the exact selected Japanese Rev0 original")
    adapter = ADAPTERS[game]
    if span(parent, HOOK, 8) != HOOK_BEFORE:
        raise GateError("native render dispatch mismatch")
    if uint(parent, adapter["slot"]) != adapter["original_text"]:
        raise GateError("first-Oak literal mismatch")
    start, end = adapter["consumer_start"], adapter["consumer_end"]
    if sha(span(parent, start, end-start)) != adapter["consumer_sha256"]:
        raise GateError("native first-Oak consumer mismatch")
    if sha(span(parent, 0x2F5C, 0x88)) != adapter["tile_sha256"]:
        raise GateError("native tile decoder mismatch")
    if any(value != 255 for value in span(parent, POOL, POOL_END-POOL)):
        raise GateError("original-only reserved pool is not entirely FF")
    artifacts, font_report = build_font(glyph_document)
    cmap = {item["unicode"]: {"_gid": int(item["glyph_id"], 0) if isinstance(item["glyph_id"], str)
                            else item["glyph_id"]} for item in glyph_document["glyphs"]}
    lines = text_lines(line)
    chars = "".join(lines)
    if (any(c not in cmap and c not in NATIVE_PUNCTUATION for c in chars) or
            not any(c in cmap for c in chars)):
        raise GateError("probe text requires allocated private characters or supported punctuation, including a private character")
    widths = [sum(16 if c in NATIVE_PUNCTUATION else 12 for c in item) for item in lines]
    # This first-line consumer uses native StringCopy, which is byte-FF-terminated.
    # Refuse such IDs rather than silently truncating; a general engine needs an adapter.
    if any(255 in cmap[c]["_gid"].to_bytes(2, "big") for c in chars if c in cmap):
        raise GateError("probe native StringCopy cannot carry glyph IDs containing FF")
    # Keep the probe visible until A/B, rather than auto-advancing on FF.
    stream = bytes.fromhex("fc0604") + b"\xfe".join(encode(item, cmap, require_end=False) for item in lines) + bytes.fromhex("faff")
    code, sources = compile_code(len(stream), arm_prefix)
    pages = font_report["pages"]
    page_locations = {page: FONT+index*0x4000 for index, page in enumerate(pages)}
    blank = FONT+len(pages)*0x4000
    page_count = max(pages)+1
    table = b"".join((BASE+page_locations.get(page, blank)).to_bytes(4, "little")
                     for page in range(page_count))
    config = b"".join(value.to_bytes(4, "little") for value in
        (BASE+TABLE, page_count, BASE+blank, 0x03003DE0, 0x03003E60, 0x08002F5D))
    if blank+0x4000 > POOL_END or TABLE+len(table) > TEXT or TEXT+len(stream) > FONT:
        raise GateError("probe layout overflow")
    product, writes = bytearray(parent), []

    def put(at, data, purpose="new_pool"):
        before = span(parent, at, len(data))
        writes.append(dict(offset=at, before_hex=before.hex(), after_hex=data.hex(), purpose=purpose))
        product[at:at+len(data)] = data

    # Eight-byte BX trampoline avoids borrowing any low-ROM font padding.
    put(HOOK, bytes.fromhex("00480047")+(BASE+CODE+1).to_bytes(4, "little"), "patch")
    put(adapter["slot"], (BASE+TEXT).to_bytes(4, "little"), "patch")
    put(CODE, code)
    put(CONFIG, config)
    put(TABLE, table)
    put(TEXT, stream)
    for page, at in page_locations.items():
        put(at, artifacts[f"page_{page:02X}.bin"])
    put(blank, artifacts["blank_page.bin"])
    result = bytes(product)
    report = verify_changes(parent, result, writes, PROTECTED)
    report.update(game=game, input_sha256=profile["sha256"], output_sha256=sha(result),
        source_sha256=sources, text_size=len(stream), glyph_count=sum(c in cmap for c in chars),
        character_count=len(chars), line_count=len(lines), line_width_budgets=widths,
        maximum_ink_width=max(widths), code_bytes=len(code), literal_slot=adapter["slot"],
        new_reservation=dict(start=POOL, end=POOL_END, includes_all_guards_and_ff_tail=True),
        runtime="UNOBSERVED", complete_translation=False, experimental_first_oak_line_only=True,
        native_width_and_placeholder_hooks_installed=False)
    return result, report
