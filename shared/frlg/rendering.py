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
        main=0x1DB3CC,metrics=0x1DB630,gate=0x1DB4C0,small=0x9D13E0,small_measure=0x7B8450,
        summary_controls=0x7B84C8,summary_hook=0x1375E8,summary_tail=0x081375F1,
        small_pages=0x9D08A0,small_widths=0x9D08D0,hook="d5f1dafd",
        gate_source="firered/patches/intro_font_gate.s",gate_tail=0x087B82A5,
        scanners=0x7C0048,width_alias=0x7C065C,secondary_gate=0xFF8308,
        fixed_entry=0x087C0048,variable_entry=0x087C006A,
        secondary_tail=0x08FF7835,
        metrics_source="firered/patches/glyph_metrics.s",prefix_bx=False),
    "leafgreen-2.3-r89":dict(
        sha256="6012bf84ffbf48f0e88c45e9f04977c7cc79ee781f79184b263d04f247f0ff56",
        main=0x1DB3A8,metrics=0x1DB49C,gate=0x6DFB14,small=0x9D1400,small_measure=0x6D5048,
        summary_controls=0x6D5000,summary_hook=0x1375C0,summary_tail=0x081375C9,
        small_pages=0x9D08C0,small_widths=0x9D08F0,hook="d5f1c8fd",
        gate_source="leafgreen/patches/storage_font_gate.s",gate_tail=0x086DF001,
        scanners=0xBC0000,secondary_gate=0x6DF000,
        fixed_entry=0x08BC0000,variable_entry=0x08BC0036,
        secondary_tail=0x08B33A09,
        metrics_source="leafgreen/patches/glyph_metrics.s",prefix_bx=True),
}
PROFILES['firered-2.4-0112']=dict(PROFILES['firered-2.3-0111'],
    sha256='ecfba3307cf02431e1c3b20e99cefb2a4f69c1fe3f2bb97077291bba63eda7c8')
PROFILES['leafgreen-2.4-r90']=dict(PROFILES['leafgreen-2.3-r89'],
    sha256='0e245669456926a59cc1f0e5fa5d87680c874998d17a6a4adab7634e975d7644')


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
            {"MAIN_FONT_ROUTE":p["gate_tail"]} if not p["prefix_bx"] else {}),
        ("small_measure",p["small_measure"],"shared/patches/small_measure_production.s",
            dict(SMALL_WIDTHS=BASE+p["small_widths"])),
        ("summary_controls",p["summary_controls"],"shared/patches/summary_controls.s",
            dict(SMALL_MEASURE=BASE+p["small_measure"],SUMMARY_CONTINUATION=p["summary_tail"]))]
    if p["prefix_bx"]:
        specifications.extend([
            ("scanners",p["scanners"],"leafgreen/patches/width_scanners.s",
             dict(CN_FONT_MAX_GID=font_pages.MAX_GID,SMALL_FULL10=1,COPY1_FULL10=1,PRIVATE_FULL12=1,
                  NATIVE_VARIABLE_FALLBACK=0x08005E29)),
            ("secondary_gate",p["secondary_gate"],"leafgreen/patches/units_font_gate.s",
             dict(SLOT_START=0x08E07500,SLOT_END=0x08E07530,OLD_GATE=p["secondary_tail"]))])
    else:
        specifications.extend([
            ("scanners",p["scanners"],"firered/patches/width_scanners.s",
             dict(WIDTH_ALIAS=BASE+p["width_alias"],CN_FONT_MAX_PAGE=font_pages.MAX_PAGE)),
            ("width_alias",p["width_alias"],"firered/patches/width_alias.s",{}),
            ("secondary_gate",p["secondary_gate"],"firered/patches/storage_font_gate.s",
             dict(OLD_FONT_GATE48=p["secondary_tail"]))])
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
        unresolved_gate_tail=p["secondary_tail"],
        known_issues=(["LeafGreen native-variable fallback0x08005E29 lands in dispatch-table data; source match is not a safety pass"]
                      if p["prefix_bx"] else []),
        missing=["remaining small-context wrappers and font-gate fallback chains",
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
    for at,want in ((0x5CA0,p["fixed_entry"]),(0x5E28,p["variable_entry"])):
        if uint(data,at)!=want:raise GateError("native width dispatch binding mismatch")
    measure_refs = ((0x6D310C,bytes.fromhex('004b184749506d08')),
                    (0x6DF0C8,bytes.fromhex('49506d08'))) if p["prefix_bx"] else (
                    (0x7B83F8,bytes.fromhex('00f02af8')),
                    (0x7B8430,bytes.fromhex('00f00ef8')))
    for at,want in measure_refs:
        if span(data,at,len(want))!=want:raise GateError('small measurement binding mismatch')
    summary_bridge=bytes.fromhex('004b1847')+(BASE+p['summary_controls']+1).to_bytes(4,'little')
    if span(data,p['summary_hook'],8)!=summary_bridge:
        raise GateError('summary controls binding mismatch')
    if not p["prefix_bx"]:
        expected_bridge=bytes.fromhex("004b1847")+(BASE+p["secondary_gate"]+1).to_bytes(4,"little")
        if span(data,p["gate_tail"]-BASE-1,8)!=expected_bridge:
            raise GateError("secondary font gate bridge mismatch")
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
