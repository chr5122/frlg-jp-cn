"""Pack caller-owned small glyphs; optional exact normal-charmap pairing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
sys.path.insert(0, str(ROOT / 'tools'))
from frlg.encode import load_charmap
from frlg.rom import GateError, sha
from frlg.small_font_pack import build_small_font
from patch_rom import load_recipe


def run(source: Path, normal_charmap: Path | None = None, output_dir: Path | None = None):
    inputs = [source] + ([normal_charmap] if normal_charmap is not None else [])
    digests = [sha(path.read_bytes()) for path in inputs]
    normal = load_charmap(normal_charmap) if normal_charmap is not None else None
    artifacts, report = build_small_font(load_recipe(source), normal)
    if any(sha(path.read_bytes()) != digest for path, digest in zip(inputs, digests)):
        raise GateError('input changed during run')
    report.update(input_sha256=digests[0], normal_charmap_sha256=digests[1] if normal is not None else None,
                  written=False)
    if output_dir is not None:
        output_dir.mkdir(exist_ok=False)
        for name, data in artifacts.items():
            target = output_dir / name
            with target.open('xb') as handle:
                handle.write(data)
            if sha(target.read_bytes()) != report['artifacts'][name]['sha256']:
                raise GateError('artifact readback mismatch; output is not validated')
        if any(sha(path.read_bytes()) != digest for path, digest in zip(inputs, digests)):
            raise GateError('input changed during write')
        report['written'] = True
        with (output_dir / 'manifest.json').open('x', encoding='utf8') as handle:
            json.dump(report, handle, ensure_ascii=True, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--glyphs', required=True, type=Path)
    parser.add_argument('--normal-charmap', type=Path, help='optional allocated normal charmap; require exact pairing')
    parser.add_argument('--output-dir', type=Path, help='new directory only; omit for dry run')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.glyphs, args.normal_charmap, args.output_dir), indent=2))
    except (GateError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
