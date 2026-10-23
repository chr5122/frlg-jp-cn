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


def dependencies(record, source, product):
    """Explicit merge base plus every parents[] input; never guess missing pins.

    Unsupported/malformed parent collections invalidate the complete edge.
    Valid subsets remain visible as evidence, not a complete build dependency.
    """
    merging = 'parents' in record
    values = [dict(role='merge_base' if merging else 'parent', **source)]
    issues = []
    if not merging:
        return values, issues
    parents = record['parents']
    if not isinstance(parents, list) or len(parents) < 2:
        return values, ['UNSUPPORTED_PARENTS_COLLECTION']
    for index, entry in enumerate(parents):
        if not isinstance(entry, dict):
            issues.append('NON_OBJECT_PARENT')
            continue
        # This historical schema uses rom for the path and name for a label.
        # Preserve path aliases so conflicts cannot be silently overwritten.
        normalized = {k: entry[k] for k in ('path', 'file', 'name', 'sha', 'sha256') if k in entry}
        value = endpoint({'input': normalized}, 'input')
        if 'rom' in entry:
            value = endpoint({'input': normalized, 'input_rom': {
                'path': entry['rom'],
                **{k: entry[k] for k in ('sha', 'sha256') if k in entry}}}, 'input')
        values.append(dict(role='branch', index=index, **value))
    hashes = [v['sha256'] for v in values if v['state'] == 'DECLARED_IDENTITY']
    if len(hashes) != len(set(hashes)):
        issues.append('DUPLICATE_BASE_OR_BRANCH_IDENTITY')
    by_name = {}
    for value in values:
        for name in value['names']:
            if value['sha256']:
                by_name.setdefault(name, set()).add(value['sha256'])
    if any(len(hashes) > 1 for hashes in by_name.values()):
        issues.append('SAME_INPUT_NAME_DIFFERENT_HASHES')
    if product['sha256'] in hashes:
        issues.append('MERGE_OUTPUT_IS_AN_INPUT')
    return values, issues


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
        inputs, issues = dependencies(body, source, product)
        for value in [source, product] + inputs:
            observed = {h for name in value['names'] for h in artifacts.get(name, [])}
            value['artifact_state'] = ('NOT_INSPECTED_OR_NOT_FOUND' if not observed else
                'IDENTITY_NOT_DECLARED' if not value['sha256'] else
                'MATCHING_AND_CONFLICTING_ARTIFACTS' if value['sha256'] in observed and len(observed) > 1 else
                'FILE_SHA_MATCH' if value['sha256'] in observed else 'PATH_NOW_DIFFERS_FROM_DECLARED_SHA')
        paired = (product['state'] == 'DECLARED_IDENTITY' and not issues
                  and all(value['state'] == 'DECLARED_IDENTITY' for value in inputs))
        result.append(dict(record_id=item['record_id'], manifest_sha256=item['manifest_sha256'],
                           state='DECLARED_HASH_EDGE' if paired else 'NEEDS_SCHEMA_OR_IDENTITY',
                           input=source, dependencies=inputs, dependency_issues=issues, output=product))
    edges = [r for r in result if r['state'] == 'DECLARED_HASH_EDGE']
    reachable, seen = set(), {target} if target else set()
    pending = list(seen)
    while pending:
        child = pending.pop()
        for r in edges:
            if r['output']['sha256'] == child:
                reachable.add(r['record_id'])
                for value in r['dependencies']:
                    parent = value['sha256']
                    if parent not in seen:
                        seen.add(parent)
                        pending.append(parent)
    producers = {r['output']['sha256'] for r in edges}
    return dict(record_count=len(result), states=dict(Counter(r['state'] for r in result)),
                input_states=dict(Counter(r['input']['state'] for r in result if 'input' in r)),
                output_states=dict(Counter(r['output']['state'] for r in result if 'output' in r)),
                target_sha256=target, target_declared_ancestry=sorted(reachable),
                target_unresolved_frontier=sorted(seen - producers),
                merge_records=sum('parents' in item['body'] for item in records if isinstance(item['body'], dict)),
                evidence_grade='MANIFEST_DECLARATIONS_WITH_OPTIONAL_FILE_SHA_CHECKS_NOT_BUILD_REPLAY',
                complete_rebuild_proven=False, records=result)
