from __future__ import annotations

from .rom import BASE, GateError, pointer, span, uint

# event.inc trainerbattle: type -> width, TEXT operands, SCRIPT operands.
# In particular, pointer3 is a SCRIPT for types 1/2, not a text slot.
TRAINERS = {0: (14, (6, 10), ()), 1: (18, (6, 10), (14,)),
            2: (18, (6, 10), (14,)), 3: (10, (6,), ()),
            4: (18, (6, 10, 14), ()), 5: (14, (6, 10), ()),
            6: (22, (6, 10, 14), (18,)), 7: (18, (6, 10, 14), ()),
            8: (22, (6, 10, 14), (18,)), 9: (14, (6, 10), ())}
TEXT_OPERANDS = {0x0F: 2, 0x67: 1, 0x85: 2, 0x9B: 1}


def walk(rom: bytes, entry: int, widths: dict, std: dict[int, int] | None = None, budget=40000) -> dict:
    """Static reachable graph, not proof an event was executed in gameplay."""
    std = std or {}
    queue, seen, slots, unknown, indirect = [entry], set(), {}, [], []

    def enqueue(v: int, origin: int):
        try:
            queue.append(pointer(rom, v))
        except GateError as e:
            unknown.append({"offset": origin, "reason": str(e)})

    def add_slot(a, so, op):
        sl, value = a + so, uint(rom, a + so)
        if value == 0:
            indirect.append({"instruction": a, "slot": sl, "opcode": op, "reason": "null message: caller loadword required"})
            return
        try:
            pointer(rom, value)
        except GateError:
            indirect.append({"instruction": a, "slot": sl, "opcode": op, "reason": "non-ROM value, not a confirmed text slot"})
            return
        slots[sl] = {"slot": sl, "instruction": a, "opcode": op, "target": value,
                     "instruction_hex": span(rom, a, (TRAINERS[rom[a + 1]][0] if op == 0x5C else widths[f'0x{op:02X}']["width"])).hex()}

    while queue and len(seen) < budget:
        a = queue.pop()
        while 0 <= a < len(rom) and a not in seen and len(seen) < budget:
            seen.add(a)
            op = rom[a]
            if op == 0x5C:
                try:
                    ty = span(rom, a + 1, 1)[0]
                    if ty not in TRAINERS:
                        raise GateError(f"unknown trainerbattle type {ty:#x}")
                    size, texts, scripts = TRAINERS[ty]
                    span(rom, a, size)
                    for so in texts:
                        add_slot(a, so, op)
                    for so in scripts:
                        if uint(rom, a + so):
                            enqueue(uint(rom, a + so), a)
                    a += size
                    continue
                except GateError as e:
                    unknown.append({"offset": a, "opcode": op, "reason": str(e)})
                    break
            spec = widths.get(f"0x{op:02X}")
            if not spec or type(spec.get("width")) is not int or spec["width"] <= 0:
                unknown.append({"offset": a, "opcode": op, "reason": "unknown/contextual width; never guessed"})
                break
            size = spec["width"]
            try:
                span(rom, a, size)
                if op in TEXT_OPERANDS:
                    if op != 0x0F or rom[a + 1] == 0:
                        add_slot(a, TEXT_OPERANDS[op], op)
                    else:
                        indirect.append({"instruction": a, "opcode": op, "reason": "loadword non-text register"})
                if op == 0x78:
                    indirect.append({"instruction": a, "opcode": op, "target": uint(rom, a + 1),
                                     "reason": "braille has formatting header; separate carrier adapter required"})
                if op in {0x02, 0x03, 0x0C, 0x0D}:
                    break
                if op in {0x04, 0x05}:
                    target = uint(rom, a + 1)
                    enqueue(target, a)
                    if op == 0x05:
                        break
                elif op in {0x06, 0x07}:
                    enqueue(uint(rom, a + 2), a)
                elif op in {0x08, 0x09, 0x0A, 0x0B}:
                    index = rom[a + (2 if op in {0x0A, 0x0B} else 1)]
                    if index in std:
                        enqueue(std[index], a)
                    else:
                        indirect.append({"instruction": a, "opcode": op, "std_id": index, "reason": "unresolved standard dispatch"})
                    if op == 0x08:
                        break  # unconditional gotostd does NOT fall through into adjacent data
                elif op in {0x23, 0x25, 0x6F, 0x70}:
                    indirect.append({"instruction": a, "opcode": op, "raw_hex": span(rom, a, size).hex(),
                                     "reason": "native/special/table consumer not modeled"})
                a += size
            except GateError as e:
                unknown.append({"offset": a, "opcode": op, "reason": str(e)})
                break
    if len(seen) >= budget and queue:
        unknown.append({"offset": entry, "reason": "WALK_BUDGET_EXHAUSTED"})
    elif len(seen) >= budget:
        unknown.append({"offset": entry, "reason": "WALK_BUDGET_LIMIT_REACHED"})
    return {"slots": slots, "unknown": unknown, "indirect": indirect, "visited": len(seen)}
