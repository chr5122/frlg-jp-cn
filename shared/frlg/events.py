from __future__ import annotations

from .rom import GateError, pointer, span, uint

# Source: pret FRLG include/global.fieldmap.h. ROM coordinates are NOT avatar +7 coordinates.
LAYOUT = {"obj": (24, 16, 4, 6, True), "warp": (8, None, 0, 2, True),
          "coord": (16, 12, 0, 2, False), "bg": (12, 8, 0, 2, False)}
FACING = {0: "any", 1: "north", 2: "south", 3: "east", 4: "west"}
SCRIPT_TAGS = {1: "on_load", 3: "on_transition", 5: "on_resume", 7: "on_return"}
TABLE_TAGS = {2: "on_frame", 4: "on_warp"}


def parse_events(rom: bytes, offset: int) -> dict:
    span(rom, offset, 20)
    result = {"tables": {}, "unknown": []}
    for index, (name, (stride, so, xo, yo, signed)) in enumerate(LAYOUT.items()):
        count, value = rom[offset + index], uint(rom, offset + 4 + index * 4)
        rows = []
        if count:
            at = pointer(rom, value)
            span(rom, at, count * stride)
            for n in range(count):
                a = at + n * stride
                rec = {"offset": a, "index": n, "raw_hex": span(rom, a, stride).hex(),
                       "x": uint(rom, a + xo, 2, signed), "y": uint(rom, a + yo, 2, signed),
                       "script": None, "role": name}
                if name == "obj":
                    rec.update(kind=rom[a + 2], flag=uint(rom, a + 20, 2))
                    # Clone templates' union encodes target object/map, not a normal movement record.
                    if rec["kind"] == 255:
                        rec.update(target_local_id=rom[a + 8], target_map_num=uint(rom, a + 12, 2),
                                   target_map_group=uint(rom, a + 14, 2), carrier="clone_object")
                if name == "coord":
                    rec.update(elevation=rom[a + 4], trigger=uint(rom, a + 6, 2), value=uint(rom, a + 8, 2))
                if name == "bg":
                    k, raw = rom[a + 5], uint(rom, a + 8)
                    rec.update(kind=k, facing=FACING.get(k))
                    if k in {5, 6, 7}:
                        rec.update(role="hidden_item", item=raw & 0xFFFF, flag=(raw >> 16) & 255,
                                   quantity=(raw >> 24) & 127, underfoot=raw >> 31)
                    elif k not in FACING:
                        rec["role"] = "unknown_bg_carrier"
                        result["unknown"].append({"offset": a, "kind": k})
                    else:
                        rec["script"] = raw
                elif so is not None:
                    rec["script"] = uint(rom, a + so)
                if rec["script"]:
                    pointer(rom, rec["script"])
                rows.append(rec)
        result["tables"][name] = rows
    return result


def parse_map_scripts(rom: bytes, value: int, budget=4096) -> dict:
    at = pointer(rom, value)
    result = {"entries": [], "unknown": [], "records": 0, "condition_tables": 0, "condition_entries": 0}
    steps = 0
    while steps < budget:
        steps += 1
        tag = span(rom, at, 1)[0]
        if not tag:
            return result
        script = uint(rom, at + 1)
        result["records"] += 1
        if tag in SCRIPT_TAGS:
            pointer(rom, script)
            result["entries"].append({"script": script, "tag": tag, "offset": at})
        elif tag in TABLE_TAGS:
            q = pointer(rom, script)
            result["condition_tables"] += 1
            while steps < budget:
                steps += 1
                var = uint(rom, q, 2)
                if not var:
                    break
                value, target = uint(rom, q + 2, 2), uint(rom, q + 4)
                pointer(rom, target)
                result["entries"].append({"script": target, "tag": tag, "var": var, "value": value, "offset": q})
                result["condition_entries"] += 1
                q += 8
            else:
                raise GateError("map condition table budget exhausted")
        else:
            result["unknown"].append({"offset": at, "tag": tag})
            # Record width known independently: safe to enumerate next record, never walk unknown target.
        at += 5
    raise GateError("map scripts budget exhausted")
