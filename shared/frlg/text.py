from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .rom import GateError

# pret FRLG include/characters.h + src/text.c; unknown subcodes are NOT zero-length.
FC_LENGTHS = {1: 1, 2: 1, 3: 1, 4: 3, 5: 1, 6: 1, 7: 0, 8: 1,
              9: 0, 10: 0, 11: 2, 12: 1, 13: 1, 14: 1, 15: 0,
              16: 2, 17: 1, 18: 1, 19: 1, 20: 1, 21: 0, 22: 0, 23: 0, 24: 0}
PUNCT = {0xAB: "！", 0xAC: "？", 0xAD: "。", 0xB0: "…", 0xF0: "："}


@dataclass(frozen=True)
class Stream:
    raw: bytes
    tokens: tuple[tuple[int, str, bytes], ...]
    status: str
    end: int


def read(data: bytes, offset: int, mode: str, budget=0x8000) -> Stream:
    if mode not in {"jp", "cn"}:
        raise GateError("text mode must be explicit: jp/cn")
    if offset < 0 or offset >= len(data):
        return Stream(b"", (), "OOB", offset)
    if budget <= 0:
        raise GateError("read budget must be positive")
    stop, i, tokens = min(len(data), offset + budget), offset, []
    while i < stop:
        b, step, kind = data[i], 1, "glyph"
        if b == 0xFF:
            tokens.append((i - offset, "end", b"\xff"))
            return Stream(data[offset:i + 1], tuple(tokens), "OK", i + 1)
        if b == 0xF7:
            step, kind = (3 if mode == "cn" else 2), ("cn" if mode == "cn" else "dynamic")
        elif b in {0xF8, 0xF9, 0xFD}:
            step, kind = 2, "parameter"
        elif b == 0xFC:
            kind = "extended"
            if i + 2 > stop:
                return Stream(data[offset:stop], tuple(tokens), "TRUNCATED_TOKEN", stop)
            sub = data[i + 1]
            if sub not in FC_LENGTHS:
                return Stream(data[offset:i + 2], tuple(tokens), "UNKNOWN_FC", i + 2)
            step = 2 + FC_LENGTHS[sub]
        elif b in {0xFA, 0xFB, 0xFE}:
            kind = "layout"
        if i + step > stop:
            return Stream(data[offset:stop], tuple(tokens), "TRUNCATED_TOKEN", stop)
        tokens.append((i - offset, kind, data[i:i + step]))
        i += step
    state = "BUDGET_EXHAUSTED" if stop < len(data) else "NO_TERMINATOR"
    return Stream(data[offset:stop], tuple(tokens), state, stop)


def exact(data: bytes, mode: str) -> Stream:
    s = read(data, 0, mode, max(1, len(data)))
    if s.status == "OK" and s.end != len(data):
        return Stream(s.raw, s.tokens, "TRAILING_BYTES", s.end)
    return s


def same_stream(a: bytes, b: bytes, mode: str) -> bool:
    x, y = read(a, 0, mode), read(b, 0, mode)
    return x.status == y.status == "OK" and x.raw == y.raw


def glyph_table(path: Path) -> dict[int, str]:
    result = {}
    with path.open(encoding="utf8", newline="") as f:
        for r in csv.DictReader(f):
            gid, ch = int(r["glyph_id"], 16), r["unicode"]
            if gid in result and result[gid] != ch:
                raise GateError(f"conflicting glyph id {gid:#x}")
            result[gid] = ch
    return result


def jp_table(path: Path) -> dict[int, str]:
    result = {0: " "}
    for line in path.read_text(encoding="utf8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, ch = line.split("=", 1)
        try:
            v = int(key.strip(), 16)
        except ValueError:
            continue
        if 0 <= v <= 255 and len(ch) == 1:
            result[v] = ch
    return result


def classify(s: Stream, glyphs: dict[int, str], native: dict[int, str], jp: Stream | None = None) -> dict:
    ids = [int.from_bytes(raw[1:], "big") for _, k, raw in s.tokens if k == "cn"]
    unknown = sorted({gid for gid in ids if gid not in glyphs})
    body = [native.get(raw[0], "") for _, k, raw in s.tokens if k == "glyph"]
    cnchars = [glyphs.get(gid, "") for gid in ids]
    kana = [c for c in body + cnchars if len(c) == 1 and 0x3040 <= ord(c) <= 0x30FF]
    native_cjk = [c for c in body if len(c) == 1 and 0x3400 <= ord(c) <= 0x9FFF]
    unknown_native = [raw[0] for _, k, raw in s.tokens if k == "glyph" and raw[0] not in native]
    parameter_match = parameters(jp) == parameters(s) if jp and jp.status == "OK" and s.status == "OK" else None
    state = ("STRUCTURE_INVALID" if s.status != "OK" else
             "UNKNOWN_GLYPH" if unknown or unknown_native else
             "UNTRANSLATED" if jp and jp.status == "OK" and jp.raw == s.raw else
             "PARAMETER_MISMATCH" if parameter_match is False else
             "MIXED" if kana and ids else "JAPANESE_RESIDUE" if kana else
             "NATIVE_BODY_REVIEW" if native_cjk else
             "QUALIFIED_CN" if ids else "FORMAT_OR_NAME_REVIEW")
    return {"state": state, "qualified": state == "QUALIFIED_CN", "read_status": s.status,
            "glyph_ids": ids, "unknown_glyph_ids": unknown, "unknown_native_bytes": unknown_native,
            "kana": kana, "native_cjk": native_cjk, "parameters_preserved": parameter_match, "byte_length": len(s.raw)}


def decode(s: Stream, glyphs: dict[int, str], native: dict[int, str], mode: str) -> str:
    out = []
    for _, k, raw in s.tokens:
        b = raw[0]
        if k == "glyph":
            out.append((PUNCT.get(b) if mode == "cn" else None) or native.get(b, f"[BYTE:{b:02X}?]"))
        elif k == "cn":
            gid = int.from_bytes(raw[1:], "big")
            out.append(glyphs.get(gid, f"[F7:{gid:04X}?]"))
        elif k == "dynamic":
            out.append(f"[F7{raw[1]:02X}]")
        elif k == "parameter":
            out.append(f"[{raw.hex().upper()}]")
        elif k == "extended":
            out.append("{RAW:" + raw.hex().upper() + "}")
        elif k == "layout":
            out.append({0xFA: "{WAIT}", 0xFB: "{PAGE}", 0xFE: "{NL}"}[b])
    return "".join(out)


def parameters(s: Stream) -> list[str]:
    return [raw.hex() for _, kind, raw in s.tokens if kind in {"parameter", "dynamic"}]
