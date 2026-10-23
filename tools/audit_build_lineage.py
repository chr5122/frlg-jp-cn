"""Read-only build-manifest audit. No script execution, ROM writes or save reads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from frlg.lineage import digest, summarize
from frlg.rom import GateError, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis', required=True, type=Path)
    ap.add_argument('--extra-record', action='append', default=[], type=Path)
    ap.add_argument('--include-fix-reports', action='store_true',
                    help='also inspect top-level fix*_report.json identity records')
    ap.add_argument('--artifact-dir', action='append', default=[], type=Path,
                    help='optional direct .gba files only; never SAV/state')
    ap.add_argument('--target-sha256')
    ap.add_argument('--summary-only', action='store_true')
    args = ap.parse_args()
    if args.target_sha256 and digest(args.target_sha256) is None:
        raise GateError('target must be a full SHA-256')
    files = sorted(set(args.analysis.glob('*manifest*.json')) | set(args.extra_record))
    if args.include_fix_reports:
        files = sorted(set(files) | set(args.analysis.glob('fix*_report.json')))
    if not files:
        raise GateError('no manifest files found')
    if len({p.name for p in files}) != len(files):
        raise GateError('duplicate record basenames would make evidence IDs ambiguous')
    records, errors, pins = [], [], []
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise GateError('manifest must be a regular local file')
        raw = path.read_bytes()
        pins.append((path, sha(raw)))
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            errors.append(dict(record_id=path.name, reason='INVALID_JSON'))
            continue
        records.append(dict(record_id=path.name, manifest_sha256=sha(raw), body=body))
    artifacts = {}
    for folder in args.artifact_dir:
        for path in sorted(folder.glob('*.gba')):
            if path.is_symlink() or not path.is_file():
                raise GateError('artifact must be a regular local file')
            raw = path.read_bytes()
            pins.append((path, sha(raw)))
            artifacts.setdefault(path.name, []).append(sha(raw))
    out = summarize(records, artifacts, args.target_sha256)
    out['json_errors'] = errors
    out['scanned_files'] = len(files)
    out['artifact_files_hashed'] = sum(len(v) for v in artifacts.values())
    for path, expected in pins:
        if sha(path.read_bytes()) != expected:
            raise GateError('input changed during audit')
    out['inputs_unchanged'] = True
    if args.summary_only:
        del out['records']
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
