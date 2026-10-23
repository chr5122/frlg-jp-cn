"""Conservative manifest identity extraction. Never infer edges from FIX numbers."""
from __future__ import annotations

import re
from collections import Counter

DIGEST = re.compile(r'[0-9a-fA-F]{64}\Z')
INPUT_FIELDS = ('input_rom', 'input', 'baseline', 'base', 'parent')
OUTPUT_FIELDS = ('output_rom', 'output', 'candidate')


def digest(value):
    return value.lower() if isinstance(value, str) and DIGEST.fullmatch(value) else None


def basename(value):
    if not isinstance(value, str):
        return None
    name = value.replace('\\', '/').rsplit('/', 1)[-1]
    return name if name.lower().endswith('.gba') else None


def endpoint(record, role):
    """Keep explicit names/hashes only. Conflicting aliases remain ambiguous.

    Top-level sha256 is accepted for output only when an output filename is
    explicitly present; never reinterpret save/source/font hashes as parents.
    """
    if role not in {'input', 'output'}:
        raise ValueError('identity role must be input or output')
    fields = INPUT_FIELDS if role == 'input' else OUTPUT_FIELDS
    candidates = []
    for field in fields:
        value = record.get(field)
        if isinstance(value, dict):
            names = {name for k in ('path', 'file', 'name') if (name := basename(value.get(k)))}
            hashes = {h for k in ('sha256', 'sha') if (h := digest(value.get(k)))}
        else:
            name = basename(value)
            names = {name} if name else set()
            keys = [field + '_sha256', field + '_sha']
            if role == 'output':
                keys += ['output_sha256', 'candidate_sha256', 'sha256', 'rom_sha256']
            hashes = {h for key in keys if (h := digest(record.get(key)))}
        if names:
            candidates.append(dict(field=field, names=sorted(names), sha256s=sorted(hashes)))
    # Older schemas pair input_rom with base_sha256. Bind global input-role
    # aliases only when there is exactly one explicit ROM name in this role.
    if role == 'input' and len({n for c in candidates for n in c['names']}) == 1:
        global_hashes = {h for k in ('input_sha256', 'baseline_sha256', 'base_sha256', 'parent_sha256')
                         if (h := digest(record.get(k)))}
        for c in candidates:
            c['sha256s'] = sorted(set(c['sha256s']) | global_hashes)
    hashes = {h for c in candidates for h in c['sha256s']}
    identified_names = {n for c in candidates if c['sha256s'] for n in c['names']}
    unbound_names = {n for c in candidates if not c['sha256s'] for n in c['names']} - identified_names
    state = ('MISSING_ENDPOINT' if not candidates else 'AMBIGUOUS_HASH' if len(hashes) > 1
             else 'MISSING_HASH' if not hashes else 'UNBOUND_ADDITIONAL_ENDPOINT' if unbound_names
             else 'DECLARED_IDENTITY')
    return dict(state=state, sha256=next(iter(hashes)) if len(hashes) == 1 else None,
                names=sorted({name for c in candidates for name in c['names']}), candidates=candidates)


def summarize(records, artifacts=None, target=None):
    """records = [{record_id, manifest_sha256, body}], artifacts = {name:[SHA]}.

    No ROM body, save name, dialogue or glyph pixels are returned. Hash edges
    are declarations, not proof the historical builder was run successfully.
    """
    artifacts = artifacts or {}
    result = []
    for item in records:
        body = item['body']
        if not isinstance(body, dict):
            result.append(dict(record_id=item['record_id'], manifest_sha256=item['manifest_sha256'],
                               state='UNSUPPORTED_ROOT'))
            continue
        source, product = endpoint(body, 'input'), endpoint(body, 'output')
        for value in (source, product):
            observed = {h for name in value['names'] for h in artifacts.get(name, [])}
            value['artifact_state'] = ('NOT_INSPECTED_OR_NOT_FOUND' if not observed else
                'IDENTITY_NOT_DECLARED' if not value['sha256'] else
                'MATCHING_AND_CONFLICTING_ARTIFACTS' if value['sha256'] in observed and len(observed) > 1 else
                'FILE_SHA_MATCH' if value['sha256'] in observed else 'PATH_NOW_DIFFERS_FROM_DECLARED_SHA')
        paired = source['state'] == product['state'] == 'DECLARED_IDENTITY'
        result.append(dict(record_id=item['record_id'], manifest_sha256=item['manifest_sha256'],
                           state='DECLARED_HASH_EDGE' if paired else 'NEEDS_SCHEMA_OR_IDENTITY',
                           input=source, output=product))
    edges = [r for r in result if r['state'] == 'DECLARED_HASH_EDGE']
    reachable, seen = set(), {target} if target else set()
    pending = list(seen)
    while pending:
        child = pending.pop()
        for r in edges:
            if r['output']['sha256'] == child:
                reachable.add(r['record_id'])
                parent = r['input']['sha256']
                if parent not in seen:
                    seen.add(parent)
                    pending.append(parent)
    return dict(record_count=len(result), states=dict(Counter(r['state'] for r in result)),
                input_states=dict(Counter(r['input']['state'] for r in result if 'input' in r)),
                output_states=dict(Counter(r['output']['state'] for r in result if 'output' in r)),
                target_sha256=target, target_declared_ancestry=sorted(reachable),
                evidence_grade='MANIFEST_DECLARATIONS_WITH_OPTIONAL_FILE_SHA_CHECKS_NOT_BUILD_REPLAY',
                complete_rebuild_proven=False, records=result)
