#!/usr/bin/env python3
"""CN 私有字库页表 —— FIX348 起的单一真源。

## 为什么有这张表

`F7 + BE u16` 私有字形的运行时寻址原先是算术公式：

    page 00     -> 0x08B01000
    page 01..08 -> 0x08B40000 + (page-1)*0x10000
    page >  08  -> 非法，回落 0x08BC0000（空白）

页 08 的最高 ID 是 `0x8FF`，用完就无处可放新字；而 0xB40000..0xBC0000 每个
bank 只有前 0x4000 被用掉（256 字 × 64 B），尾部 0xC000 一直是全 FF。FIX348
把「页号 → 页基址」从算术公式改成一张 11 项页表：前 9 页逐字节保持原样，
页 09/0A 直接落在 bank B6 尾部的全 FF 区，扩容不需要动渲染器、字表、原生
字体、字宽表或存档区。

## 任何改动都要从这里取值

改私用 ID 上限、改页基址、加页、改空白页的地方（ROM 钩子源码、字模写入器、
charmap 分配器、验收脚本）都必须 import 本模块，禁止再写字面量。

## ROM 侧实体

- 页表本体：ROM 偏移 `0x00B74000`，11 × u32（page 0..0x0A），小端，
  0x08xxxxxx 形态（bit24 置位，与原有 0x08B40000 一致）。
- 空白页：ROM 偏移 `0x00B6C000`，0x4000 全 FF；非法页只读它，绝不落到原生
  字体槽。
- 解码器钩子：ROM 偏移 `0x1DB3A8`（源 `scripts/mvp08_chinese_hook.s`）
  - `0x1DB3D2` 页面上限立即数 `cmp r7, #CN_FONT_MAX_PAGE`
  - 字面量池 `0x1DB480` = 页表指针（0x08B74000），`0x1DB484` = 空白页
- 字宽天花板：ROM 偏移 `0xBC00FC` 的字面量 = `CN_FONT_MAX_GID`
  （源 `scripts/f7_pc_bag_item_width_hook.s`，定宽/变宽两入口共用这一个字面量）

## 页内布局（不变）

    addr = page_base + ((id & 0xFF) >> 3) * 0x200 + (id & 7) * 0x20
    每个字形 64 B：上半 32 B 在 addr，下半 32 B 在 addr + 0x100

旧页（01..08）的 bank 里另有 normal/female/bold 副本，位于 +0x4000/+0x8000/
+0xC000；新页（09/0A）只放一份（male 位置），因此对这两个页禁止非 male 变体
写入 —— 见 `check_variant_allowed()`。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# ---------------------------------------------------------------- ROM 侧常量
ROM_BASE = 0x08000000

PAGE0_BASE_ROM = 0x00B01000          # 页 00 的原生私有字库（8x8/小字路径也用它）
LEGACY_PAGE1_BASE_ROM = 0x00B40000   # 页 01 起，每页 0x10000
LEGACY_LAST_PAGE = 0x08              # 页 08 = 旧上限（gid 0x8FF）

# FIX348 新增两个页，落在 bank B6 尾部的全 FF 区
NEW_PAGES: Dict[int, int] = {
    0x09: 0x00B64000,
    0x0A: 0x00B68000,
}

PAGE_TABLE_ROM = 0x00B74000          # 页表本体（11 × u32）；0x4000 保留
BLANK_PAGE_ROM = 0x00B6C000          # 非法页回落用的全 FF 空白页

# 每页承载 256 个字形，占 0x4000 字节
GLYPH_BYTES = 0x40
GLYPHS_PER_PAGE = 0x100
PAGE_SPAN = GLYPHS_PER_PAGE * GLYPH_BYTES   # 0x4000

# 旧页 bank 内的变体偏移（新页不适用）
LEGACY_VARIANT_OFFSETS: Dict[str, int] = {
    "male": 0x0000,
    "normal": 0x4000,
    "female": 0x8000,
    "bold": 0xC000,
}
NEW_PAGE_VARIANTS: Tuple[str, ...] = ("male",)

MAX_PAGE = max(NEW_PAGES)                        # 0x0A
MAX_GID = (MAX_PAGE << 8) | 0xFF                 # 0x0AFF
FIRST_NEW_GID = min(NEW_PAGES) << 8              # 0x0900

# 分配器必须永久保留的块：禁止任何 normal/female/bold 变体写入、禁止被当成
# 普通字模空位回收。
RESERVED_BLOCKS: Tuple[Tuple[int, int, str], ...] = (
    (0x00B64000, 0x00B68000, "cn_page_09"),
    (0x00B68000, 0x00B6C000, "cn_page_0A"),
    (0x00B6C000, 0x00B70000, "cn_blank_page"),
    (0x00B74000, 0x00B78000, "cn_page_table"),
)
# 注：0x00B70000..0x00B74000 是已占用区（非全 FF），不列入保留块。
# 未用尽的旧页尾（0xB40000 段的 +0x4000..+0xFFFF）留待后续批次按同一页表扩展。

# 解码器 / 字宽钩子里写的立即数上限
DECODER_MAX_PAGE = MAX_PAGE
WIDTH_MAX_GID = MAX_GID


# ------------------------------------------------------------------- 页基址
def glyph_slot_in_page(gid_low: int) -> int:
    """页内偏移：低字节 -> 页内 64 字节槽。"""
    if not 0 <= gid_low <= 0xFF:
        raise ValueError(f"gid low byte out of range: 0x{gid_low:X}")
    return ((gid_low >> 3) << 9) + ((gid_low & 7) << 5)


def page_base_rom(page: int) -> int:
    """页号 -> 页基址（ROM 偏移形态）。旧页保持原公式。"""
    if page == 0:
        return PAGE0_BASE_ROM
    if 1 <= page <= LEGACY_LAST_PAGE:
        return LEGACY_PAGE1_BASE_ROM + (page - 1) * 0x10000
    if page in NEW_PAGES:
        return NEW_PAGES[page]
    raise ValueError(f"page not mapped: 0x{page:02X} (max 0x{MAX_PAGE:02X})")


def page_of(gid: int) -> int:
    return (gid >> 8) & 0xFF


def is_new_page_gid(gid: int) -> bool:
    return FIRST_NEW_GID <= gid <= MAX_GID


def check_variant_allowed(gid: int, variant: str) -> None:
    """新页只有一份字模；非 male 变体会写到别的字脸上，必须拒绝。"""
    if not 0 <= gid <= MAX_GID:
        raise ValueError(f"gid 0x{gid:04X} exceeds CN_FONT_MAX_GID 0x{MAX_GID:04X}")
    if is_new_page_gid(gid) and variant not in NEW_PAGE_VARIANTS:
        raise ValueError(
            f"gid 0x{gid:04X} lives on FIX348 page 0x{page_of(gid):02X}, which holds only "
            f"the {NEW_PAGE_VARIANTS[0]!r} copy; refusing variant {variant!r} "
            f"(would clobber the reserved page block)"
        )


def glyph_slot_rom(gid: int, variant: str = "male") -> int:
    """字形 64 字节槽的 ROM 偏移（与运行时解码器同一算式）。"""
    check_variant_allowed(gid, variant)
    if gid <= 0xFF:
        raise ValueError(f"gid 0x{gid:04X} is a page-00 slot; use the native page-00 table")
    page = page_of(gid)
    base = page_base_rom(page)
    off = glyph_slot_in_page(gid & 0xFF)
    if page <= LEGACY_LAST_PAGE:
        off += LEGACY_VARIANT_OFFSETS[variant]
    address = base + off
    if page <= LEGACY_LAST_PAGE and reserved_overlaps(address, address + 0x120):
        raise ValueError('legacy variant overlaps a later reserved font window')
    return address


# --------------------------------------------------------------- 页表字节
def page_table_values() -> List[int]:
    """页表内容：pages 0..MAX_PAGE 的基址（0x08xxxxxx 形态）。"""
    return [ROM_BASE | page_base_rom(p) for p in range(0, MAX_PAGE + 1)]


def page_table_bytes() -> bytes:
    return b"".join(v.to_bytes(4, "little") for v in page_table_values())


def page_table_size() -> int:
    return 4 * (MAX_PAGE + 1)


def page_table_patch(rom: bytes) -> bytes:
    """返回页表应当写入 ROM 的字节（带基本自检）。"""
    payload = page_table_bytes()
    if len(payload) != page_table_size():
        raise AssertionError("page table size mismatch")
    if PAGE_TABLE_ROM + len(payload) > len(rom):
        raise AssertionError("page table outside ROM")
    return payload


# --------------------------------------------------------------- 分配器口径
def allocatable_gids(start: int = 0x100) -> range:
    """可分配的 gid 范围（含 FIX348 新页）。"""
    return range(start, MAX_GID + 1)


def reserved_overlaps(lo: int, hi: int) -> List[str]:
    """给定 ROM 区间 [lo, hi) 落在哪些保留块里（写入器用来拒绝）。"""
    return [name for (rlo, rhi, name) in RESERVED_BLOCKS if lo < rhi and rlo < hi]


if __name__ == "__main__":  # 便于人工核对：python3 scripts/cn_font_pages.py
    print(f"MAX_PAGE=0x{MAX_PAGE:02X} MAX_GID=0x{MAX_GID:04X} FIRST_NEW_GID=0x{FIRST_NEW_GID:04X}")
    print(f"page_table @ 0x{PAGE_TABLE_ROM:06X} ({page_table_size()} B) blank @ 0x{BLANK_PAGE_ROM:06X}")
    for p, v in zip(range(0, MAX_PAGE + 1), page_table_values()):
        tag = "legacy" if p <= LEGACY_LAST_PAGE else "FIX348"
        print(f"  page 0x{p:02X} -> 0x{v:08X}  {tag}")
    for gid in (0x8FE, 0x8FF, 0x900, 0x9FF, 0xA00, 0xAFF):
        try:
            print(f"  gid 0x{gid:04X} slot 0x{glyph_slot_rom(gid):06X}")
        except ValueError as exc:
            print(f"  gid 0x{gid:04X} rejected: {exc}")
