"""Bounded GBA type-0x10 resource decoder. No game resource bytes bundled."""
from .rom import GateError, span


def decompress(data: bytes, start: int = 0, max_output=0x100000):
    header = span(data, start, 4)
    if header[0] != 0x10:
        raise GateError('not a type-0x10 GBA LZ77 resource')
    size = int.from_bytes(header[1:], 'little')
    if not 0 < size <= max_output:
        raise GateError('invalid or excessive decompressed size')
    out, pos = bytearray(), start + 4
    while len(out) < size:
        flags = span(data, pos, 1)[0]
        pos += 1
        for bit in range(8):
            if flags & (0x80 >> bit):
                first, second = span(data, pos, 2)
                pos += 2
                length = (first >> 4) + 3
                distance = (((first & 15) << 8) | second) + 1
                if distance > len(out):
                    raise GateError('invalid LZ77 back-reference')
                if len(out) + length > size:
                    raise GateError('LZ77 token exceeds declared output')
                for _ in range(length):
                    out.append(out[-distance])
            else:
                out.extend(span(data, pos, 1))
                pos += 1
            if len(out) == size:
                break
    return bytes(out), pos - start
