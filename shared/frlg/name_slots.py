"""Fixed display-name slots; reuse the shared tokenizer, never byte-scan EOS."""
from __future__ import annotations

from .encode import encode
from .font_pages import MAX_GID
from .rom import GateError, sha, span
from .text import read


def audit_names(data: bytes, offset: int, count: int, stride: int = 16):
    if any(type(value) is not int for value in (offset, count, stride)) or count <= 0 or stride <= 0:
        raise GateError("positive integer count/stride and bounded offset required")
    table = span(data, offset, count*stride)
    lengths, widths = {}, {}
    for index in range(count):
        stream = read(table, index*stride, "cn", stride)
        if stream.status != "OK" or any(kind not in {"glyph", "cn", "end"} for _,kind,_ in stream.tokens):
            raise GateError(f"name slot {index}: invalid structure or control in display name")
        if len(stream.tokens) == 1:
            raise GateError(f"name slot {index}: empty display name")
        for _,kind,raw in stream.tokens:
            if kind == "cn" and int.from_bytes(raw[1:], "big") > MAX_GID:
                raise GateError(f"name slot {index}: glyph ID outside current font range")
        if 255 in stream.raw[:-1]:
            raise GateError(f"name slot {index}: native byte-FF copier would truncate a token")
        length, symbols = len(stream.raw), len(stream.tokens)-1
        lengths[length] = lengths.get(length,0)+1
        widths[symbols] = widths.get(symbols,0)+1
    return dict(entries=count, stride=stride, table_sha256=sha(table),
                max_bytes_including_end=max(lengths), byte_length_histogram=lengths,
                symbol_count_histogram=widths, slot_padding="NOT_REQUIRED_TO_BE_FF",
                translation_quality="NOT_REVIEWED", runtime="UNOBSERVED")


def pack_names(names: list[str], charmap: dict, *, count: int, stride: int = 16):
    if not isinstance(names,list) or type(count) is not int or len(names) != count or count <= 0:
        raise GateError("provide exactly the declared display-name count")
    if type(stride) is not int or stride <= 0:
        raise GateError("positive integer stride required")
    records=[]
    for index,name in enumerate(names):
        if not isinstance(name,str):
            raise GateError(f"name slot {index}: Unicode string required")
        encoded=encode(name,charmap)
        if len(encoded)>stride:
            raise GateError(f"name slot {index}: name exceeds slot capacity including end")
        records.append(encoded.ljust(stride,b"\xff"))
    result=b"".join(records)
    return result,audit_names(result,0,count,stride)
