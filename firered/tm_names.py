"""Mature BUILD0100 TM read/write routes, retained by formal2.3/BUILD0111.

The build stage requires its exact prepared0099 parent, NOT a Japanese original.
verify checks source/ABI dependencies in a pinned release without writing it.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"shared"))
from frlg.name_slots import audit_names
from frlg.rom import GateError, Image, sha, span, uint, verify_changes

PARENT_SHA="318c1737153e6b4d66d98485ba44e268d65722b87c1b45fd7f981779b4c79c27"
PRODUCT_SHA="b4d067c5dc9e00f302a7cfdcafa18fe4a9fac8491a2130b01ad3e1d6654a0de0"
RELEASES={"build0100":PRODUCT_SHA,
          "2.3-build0111":"9c92e22573fad9432fe5c64c0c9c810eb504ce73a8660ceff8f7282714b48b6d"}
CODE=0xED9400
CODE_SHA="489ea427b27f709712f56db5232ff42e1fef84e74a13572a7d15f9c47f1928a7"
TABLE=0x71F444
TABLE_SHA="437ebe6434734253fdef313789053d7cf0fc728cc15d064ce6f850ce7fe32607"
BEFORE={0x11CDD0:"891800f08ffd201c",0x11CF00:"064a891800f0fcfc",0x11D904:"2994ed08"}
AFTER={0x11CDD0:"004b18471994ed08",0x11CF00:"004b18473194ed08",0x11D904:"0594ed08"}
DEPENDENCIES=[
    (0x8900,0x1E,"9f256aa82c7b59268956fe86bca001d2bad212728554d3b809ca7604007bc1f2","byte-FF StringCopy"),
    (0x11D8B0,0x14,"0b7f0baf39942ad997cba2ed2707a0a262b16edd11b34c7cb292e54a9ea207a4","native task-object lookup"),
    (0x11CDD8,0x20,"32167e1e1fe1b273bc14271863adf84f17442fc5168794600710822a9b56a6ce","forgotten continuation"),
    (0x11CF08,0x1C,"c6e3f77f5180d15189c559ecb036993b6f8b4d96c6e72b77ceeba3b41c01c10b","teach continuation")]


def compile_routes(prefix="arm-none-eabi-"):
    source=ROOT/"firered/patches/tm_names.s"
    with tempfile.TemporaryDirectory() as directory:
        temp=Path(directory);obj,elf,binary=(temp/name for name in ("routes.o","routes.elf","routes.bin"))
        for command in ([prefix+"as","-mcpu=arm7tdmi","-mthumb",str(source),"-o",str(obj)],
                        [prefix+"ld",f"-Ttext={0x08000000+CODE:#x}","-e","forgotten_get",str(obj),"-o",str(elf)],
                        [prefix+"objcopy","-O","binary","--only-section=.text",str(elf),str(binary)]):
            subprocess.run(command,check=True,capture_output=True)
        payload=binary.read_bytes()
    if len(payload)!=96 or sha(payload)!=CODE_SHA:
        raise GateError("compiled mature routes identity mismatch")
    return payload


def dependencies(data: bytes):
    for at,length,digest,label in DEPENDENCIES:
        if sha(span(data,at,length))!=digest:
            raise GateError(f"dependency mismatch: {label}")
    if uint(data,0x11CE60)!=0x28D4:
        raise GateError("native task object allocation changed")
    if (span(data,0x11CDCC,2)!=bytes.fromhex("2901") or
            span(data,0x11CEF8,2)!=bytes.fromhex("0904") or
            span(data,0x11CEFE,2)!=bytes.fromhex("090b")):
        raise GateError("TM name lookup is not the prepared16-byte stride")
    if span(data,0x11D8F4,12)!=bytes.fromhex("004b18470194ed08c046c046"):
        raise GateError("forgotten getter binding mismatch")
    if span(data,0xED9464,412)!=b"\xff"*412:
        raise GateError("full inherited reserved FF tail changed")
    names=audit_names(data,TABLE,355,16)
    if names["table_sha256"]!=TABLE_SHA:
        raise GateError("existing355-name table identity mismatch")
    return names


def verify_feature(data: bytes, revision="2.3-build0111", *, arm_prefix="arm-none-eabi-"):
    if revision not in RELEASES or len(data)!=0x1000000 or sha(data)!=RELEASES[revision]:
        raise GateError("unsupported or mismatched release identity")
    names=dependencies(data)
    for at,raw in AFTER.items():
        if span(data,at,len(bytes.fromhex(raw)))!=bytes.fromhex(raw):
            raise GateError(f"route binding mismatch at {at:#x}")
    payload=compile_routes(arm_prefix)
    if span(data,CODE,100)!=payload+b"\xff"*4:
        raise GateError("release machine code does not match public source")
    return dict(status="SOURCE_AND_DEPENDENCIES_MATCH",revision=revision,sha256=sha(data),
        names=names,code_bytes=len(payload),reserved_window=[CODE,0xED9600],
        forgotten_buffer=[0x1C0,0x1D0],teach_buffer=[0x1D0,0x1E0],
        runtime="UNOBSERVED",hardware_certified=False,complete_translation_build=False)


def patch(parent: bytes, *, arm_prefix="arm-none-eabi-"):
    if len(parent)!=0x1000000 or sha(parent)!=PARENT_SHA:
        raise GateError("requires exact prepared BUILD0099; not an original-ROM installer")
    dependencies(parent)
    for at,raw in BEFORE.items():
        if span(parent,at,len(bytes.fromhex(raw)))!=bytes.fromhex(raw):
            raise GateError(f"writer/getter preimage mismatch at {at:#x}")
    if sha(span(parent,CODE,100))!="9db0e5f36d400a00b9dcf83aac92aa6e8d90ed4a24d94b2e5d11fd24bf90e403":
        raise GateError("old100-byte route payload identity mismatch")
    payload=compile_routes(arm_prefix)
    product,writes=bytearray(parent),[]
    for at,raw in [(a,bytes.fromhex(v)) for a,v in AFTER.items()]+[(CODE,payload+b"\xff"*4)]:
        writes.append(dict(offset=at,before_hex=span(parent,at,len(raw)).hex(),after_hex=raw.hex(),purpose="display_code"))
        product[at:at+len(raw)]=raw
    result=bytes(product)
    report=verify_changes(parent,result,writes,[dict(start=0xED9464,end=0xED9600,name="owned FF tail")])
    if sha(result)!=PRODUCT_SHA or report["changed_bytes"]!=106:
        raise GateError("BUILD0100 result identity/delta mismatch")
    return result,dict(**report,sha256=PRODUCT_SHA,new_allocations=0,runtime="UNOBSERVED",complete_translation_build=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("verify","build"))
    parser.add_argument("--rom",type=Path,required=True)
    parser.add_argument("--revision",choices=tuple(RELEASES),default="2.3-build0111")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--arm-prefix",default="arm-none-eabi-")
    args=parser.parse_args()
    if args.mode=="verify" and args.output:parser.error("verify is read-only")
    try:
        expected=PARENT_SHA if args.mode=="build" else RELEASES[args.revision]
        image=Image.load(args.rom,expected,0x1000000)
        if args.mode=="verify":report=verify_feature(image.data,args.revision,arm_prefix=args.arm_prefix)
        else:
            product,report=patch(image.data,arm_prefix=args.arm_prefix)
            image.unchanged();report["output_written"]=False
            if args.output:
                if args.output.resolve()==image.path:raise GateError("refusing to overwrite input")
                with args.output.open("xb") as output:output.write(product)
                if sha(args.output.read_bytes())!=PRODUCT_SHA:raise GateError("output readback mismatch")
                report["output_written"]=True
        image.unchanged()
        print(json.dumps(report,indent=2))
    except (GateError,OSError,ValueError,subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}",file=sys.stderr);return 1
    return 0


if __name__=="__main__":sys.exit(main())
