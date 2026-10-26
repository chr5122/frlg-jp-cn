"""Synthetic external-manifest fixtures; no historical translated body."""
import copy
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg.rom import GateError,sha

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('revisions553',ROOT/'leafgreen/rebuild_revisions553.py')
rev=importlib.util.module_from_spec(sp);sp.loader.exec_module(rev)


class Revisions553Tests(unittest.TestCase):
    def test_historical_ellipsis_and_exact_control_aliases(self):
        cmap={'甲':{'_gid':1}}
        for literal,expected in [('…',2),('……',2),('………',4)]:
            self.assertEqual(rev.historical_encode(literal,cmap),b'\xb0'*expected+b'\xff')
        self.assertEqual(rev.historical_encode('甲{FD01}{FD06}{RAW:FC0B5601}',cmap),
            bytes.fromhex('f70001 fd01 fd06 fc0b5601 ff'))

    def test_other_raw_and_unknown_tokens_never_enabled(self):
        for value in ['{RAW:FA}','{RAW:FC0B5701}','{FD02}','{BOGUS}','甲{END}甲']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                rev.historical_encode(value,{'甲':{'_gid':1}})

    def fixture(self):
        cmap={'甲':{'_gid':1},'乙':{'_gid':2}}
        parent=bytearray(b'\xff'*rev.SIZE)
        old='甲…{RAW:FC0B5601}'
        new='乙…{NL}{RAW:FC0B5601}'
        oldbytes=rev.historical_encode(old,cmap);newbytes=rev.historical_encode(new,cmap)
        parent[0:4]=struct.pack('<I',0x08000020);parent[0x20:0x20+len(oldbytes)]=oldbytes
        expected=bytearray(parent);at=0xE372B8
        expected[at:at+len(newbytes)]=newbytes;expected[0:4]=struct.pack('<I',0x08000000+at)
        body=dict(fix=553,sha256=sha(expected),entries=[dict(old_stream='0x20',new_stream=hex(at),
            old=old,new=new,slots=['0x0'],bytes=len(newbytes))])
        return bytes(parent),body,cmap,bytes(expected)

    def invoke(self,parent,body,cmap,expected):
        raw=json.dumps(body).encode();changed=sum(a!=b for a,b in zip(parent,expected))
        with patch.multiple(rev,PARENT_SHA=sha(parent),OUTPUT_SHA=sha(expected),MANIFEST_SHA=sha(raw),
                            ENTRY_COUNT=len(body['entries']),CHANGED_BYTES=changed):
            return rev.build(parent,raw,cmap)

    def test_full_fixture_and_input_immutable(self):
        p,b,c,e=self.fixture();out,report=self.invoke(p,b,c,e)
        self.assertEqual(out,e);self.assertEqual(report['write_ranges'],2)
        self.assertEqual(p[0xE372B8:0xE372BC],b'\xff'*4)

    def test_old_full_stream_and_live_pointer_rejected(self):
        p,b,c,e=self.fixture()
        bad=copy.deepcopy(b);bad['entries'][0]['old']='乙…{RAW:FC0B5601}'
        with self.assertRaises(GateError):self.invoke(p,bad,c,e)
        q=bytearray(p);q[0]^=1
        with self.assertRaises(GateError):self.invoke(bytes(q),b,c,e)
        badmap={k:dict(v) for k,v in c.items()};badmap['甲']['_gid']=3
        with self.assertRaises(GateError):self.invoke(p,b,badmap,e)

    def test_nonff_guard_capacity_alignment_and_overlap(self):
        p,b,c,e=self.fixture();at=0xE372B8;size=b['entries'][0]['bytes']
        for offset in [at,at+size+3]:
            q=bytearray(p);q[offset]=0
            with self.subTest(offset=offset),self.assertRaises(GateError):self.invoke(bytes(q),b,c,e)
        for key,value in [('bytes',size-1),('new_stream','0xe372b9'),('new_stream','0x1000')]:
            bad=copy.deepcopy(b);bad['entries'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(GateError):self.invoke(p,bad,c,e)
        bad=copy.deepcopy(b);bad['entries']*=2
        with self.assertRaises(GateError):self.invoke(p,bad,c,e)

    def test_final_identity_and_delta_counts_rejected(self):
        p,b,c,e=self.fixture();raw=json.dumps(b).encode()
        for kwargs in [dict(OUTPUT_SHA='0'*64),dict(CHANGED_BYTES=0)]:
            params=dict(PARENT_SHA=sha(p),OUTPUT_SHA=sha(e),MANIFEST_SHA=sha(raw),ENTRY_COUNT=1,
                        CHANGED_BYTES=sum(a!=z for a,z in zip(p,e)));params.update(kwargs)
            with patch.multiple(rev,**params),self.assertRaises(GateError):rev.build(p,raw,c)

    def test_parent_manifest_identity_and_readonly_cli(self):
        with self.assertRaises(GateError):rev.build(b'not a game',b'{broken',{})
        p,b,c,e=self.fixture();raw=json.dumps(b).encode()
        with patch.object(rev,'PARENT_SHA',sha(p)),self.assertRaises(GateError):rev.build(p,raw+b' ',c)
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'fixture.gba';f.write_bytes(b'not a game')
            q=subprocess.run([sys.executable,'-B',str(ROOT/'leafgreen/rebuild_revisions553.py'),
                '--parent',str(f),'--manifest',str(f),'--charmap',str(f)],capture_output=True,text=True)
            self.assertNotEqual(q.returncode,0);self.assertIn('identity mismatch',q.stderr)
            self.assertEqual(list(Path(tmp).iterdir()),[f])


if __name__=='__main__':unittest.main()
