"""Compile selected CURRENT production renderer components; read-only ROM audit.

This deliberately does not install an engine or bundle font bitmaps.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from . import font_pages
from .rom import BASE, GateError, pointer, sha, span, uint

ROOT=Path(__file__).resolve().parents[2]
PROFILES={
    "firered-2.3-0111":dict(
        sha256="9c92e22573fad9432fe5c64c0c9c810eb504ce73a8660ceff8f7282714b48b6d",
        main=0x1DB3CC,metrics=0x1DB630,gate=0x1DB4C0,small=0x9D13E0,
        small_pages=0x9D08A0,small_widths=0x9D08D0,hook="d5f1dafd",
        gate_source="firered/patches/intro_font_gate.s",gate_tail=0x087B82A5,
        metrics_source="firered/patches/glyph_metrics.s",prefix_bx=False),
    "leafgreen-2.3-r89":dict(
        sha256="6012bf84ffbf48f0e88c45e9f04977c7cc79ee781f79184b263d04f247f0ff56",
        main=0x1DB3A8,metrics=0x1DB49C,gate=0x6DFB14,small=0x9D1400,
        small_pages=0x9D08C0,small_widths=0x9D08F0,hook="d5f1c8fd",
        gate_source="leafgreen/patches/storage_font_gate.s",gate_tail=0x086DF001,
        metrics_source="leafgreen/patches/glyph_metrics.s",prefix_bx=True),
}


def _assemble(source: str, base: int, definitions: dict, prefix: str):
    with tempfile.TemporaryDirectory() as directory:
        tmp=Path(directory);obj,elf,binary=(tmp/name for name in ("module.o","module.elf","module.bin"))
        flags=[item for key,value in definitions.items() for item in ("--defsym",f"{key}={value}")]
        commands=[
            [prefix+"as","-mcpu=arm7tdmi","-mthumb",*flags,str(ROOT/source),"-o",str(obj)],
            [prefix+"ld",f"-Ttext={BASE+base:#x}","-e",f"{BASE+base:#x}",str(obj),"-o",str(elf)],
            [prefix+"objcopy","-O","binary","--only-section=.text",str(elf),str(binary)]]
        for command in commands:subprocess.run(command,check=True,capture_output=True,timeout=30)
        return binary.read_bytes()


def compile_components(profile: str, *, arm_prefix="arm-none-eabi-"):
    if profile not in PROFILES:raise GateError("unknown production renderer profile")
    p=PROFILES[profile]
    definitions=dict(CN_FONT_MAX_PAGE=font_pages.MAX_PAGE,
        CN_FONT_PAGE_TABLE=BASE+font_pages.PAGE_TABLE_ROM,
        CN_FONT_BLANK_PAGE=BASE+font_pages.BLANK_PAGE_ROM,
        PREFIX_ROUTE=BASE+p["gate"],MAIN_METRICS=BASE+p["metrics"])
    if p["prefix_bx"]:definitions["PREFIX_USES_BX"]=1
    specifications=[
        ("main",p["main"],"shared/patches/cn_main_production.s",definitions),
        ("small",p["small"],"shared/patches/cn_small_production.s",
            dict(CN_FONT_MAX_GID=font_pages.MAX_GID,SMALL_PAGES=BASE+p["small_pages"],
                 SMALL_WIDTHS=BASE+p["small_widths"],MAIN_DRAW=BASE+p["main"]+0x23)),
        ("metrics",p["metrics"],p["metrics_source"],{}),
        ("gate",p["gate"],p["gate_source"],
            {"MAIN_FONT_ROUTE":p["gate_tail"]} if not p["prefix_bx"] else {})]
    payloads,rows={},[]
    for name,at,source,defs in specifications:
        raw=_assemble(source,at,defs,arm_prefix)
        if not raw or len(raw)>512:raise GateError(f"unexpected {name} payload size")
        payloads[name]=raw
        rows.append(dict(name=name,offset=at,bytes=len(raw),sha256=sha(raw),source=source,
                         source_sha256=sha((ROOT/source).read_bytes())))
    if len(payloads["main"])!=244 or len(payloads["small"])!=108:
        raise GateError("production decoder layout drift")
    return payloads,dict(profile=profile,components=rows,rom_installed=False,
        runtime="UNOBSERVED",complete_renderer_export=False,
        unresolved_gate_tail=p["gate_tail"],
        missing=["general measurement/scanning and full gate fallback chain",
                 "external licensed normal/small glyph bitmaps and width resources",
                 "clean-original production installation/orchestration"])


def verify(data: bytes, profile: str, *, arm_prefix="arm-none-eabi-"):
    if profile not in PROFILES:raise GateError("unknown production renderer profile")
    p=PROFILES[profile]
    if len(data)!=0x1000000 or sha(data)!=p["sha256"]:
        raise GateError("production ROM identity mismatch")
    payloads,report=compile_components(profile,arm_prefix=arm_prefix)
    if span(data,0x5814,4)!=bytes.fromhex(p["hook"]):raise GateError("native RenderText binding mismatch")
    for row in report["components"]:
        if span(data,row["offset"],row["bytes"])!=payloads[row["name"]]:
            raise GateError(f"compiled {row['name']} does not match live production component")
    expected=font_pages.page_table_bytes()
    if span(data,font_pages.PAGE_TABLE_ROM,len(expected))!=expected:
        raise GateError("normal font page table mismatch")
    blank=span(data,font_pages.BLANK_PAGE_ROM,font_pages.PAGE_SPAN)
    if blank!=b"\xff"*len(blank):raise GateError("normal fallback page is not blank")
    small_table=span(data,p["small_pages"],4*(font_pages.MAX_PAGE+1))
    page_offsets=[]
    for page in range(font_pages.MAX_PAGE+1):
        at=pointer(data,uint(small_table,4*page))
        span(data,at,font_pages.PAGE_SPAN)
        page_offsets.append(at)
    widths=span(data,p["small_widths"],font_pages.MAX_GID+1)
    if any(value>16 for value in widths):raise GateError("small glyph width outside16-pixel canvas")
    report.update(status="SELECTED_PRODUCTION_SOURCE_MATCH",rom_sha256=sha(data),
        normal_page_table_sha256=sha(expected),small_page_table_sha256=sha(small_table),
        small_width_table_sha256=sha(widths),small_page_offsets=page_offsets,
        small_width_range=[min(widths),max(widths)],font_bitmaps_redistributed=False,
        allocation_performed=False,hardware_certified=False)
    return report
