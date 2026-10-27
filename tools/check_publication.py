"""Fail-closed publication allowlist. A heuristic scan is not a legal audit."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = frozenset("""
.gitignore .github/workflows/check.yml LICENSE README.md NOTICE.md CONTRIBUTING.md Makefile
.github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md .github/pull_request_template.md
docs/GETTING_STARTED.md docs/DEPENDENCIES.md docs/ROADMAP.md
tools/check.py tests/test_check_runner.py
tools/patch_rom.py shared/frlg/patching.py tests/test_patching.py docs/EDIT_ORIGINAL.md
tools/build_font.py shared/frlg/font_pack.py shared/patches/cn_glyph.s
tests/test_font_pack.py docs/FONT_PIPELINE.md
shared/frlg/original_probe.py shared/patches/cn_original_probe.s
tools/build_original_probe.py tests/test_original_probe.py docs/ORIGINAL_PROBE.md
firered/patches/tm_names.s firered/tm_names.py shared/frlg/name_slots.py
tools/check_tm_cpu.py tests/test_tm_names.py tests/tm_cpu.c tests/fixtures/tm_copy.s docs/TM_NAMES.md
shared/frlg/rendering.py tools/renderer_module.py tests/test_rendering.py docs/RENDERING_MODULE.md
shared/patches/cn_main_production.s shared/patches/cn_small_production.s
firered/patches/glyph_metrics.s firered/patches/intro_font_gate.s
leafgreen/patches/glyph_metrics.s leafgreen/patches/storage_font_gate.s
firered/patches/width_scanners.s firered/patches/width_alias.s firered/patches/storage_font_gate.s
leafgreen/patches/width_scanners.s leafgreen/patches/units_font_gate.s
tests/width_cpu.c tools/check_width_cpu.py
docs/WIDTH_SCANNERS.md
docs/BUILDING.md docs/COMPATIBILITY.md docs/PUBLICATION_SCOPE.md docs/SOURCE_PROVENANCE.json docs/VALIDATION.md
docs/LEAFGREEN_ORIGIN.md docs/LEAFGREEN_ORIGIN_EVIDENCE.json docs/BUILD_CHAIN.json
docs/LEAFGREEN_1_0_LINEAGE.md docs/LEAFGREEN_1_0_LINEAGE_SUMMARY.json
docs/LEAFGREEN_ARCHIVE_REPLAY.json
docs/LEAFGREEN_LAYOUT_REPLAY.json
docs/LEAFGREEN_REVISIONS_REPLAY.json
docs/lineage_verified/fix557.json docs/lineage_verified/fix558.json docs/lineage_verified/fix559.json
docs/lineage_verified/fix555.json docs/lineage_verified/fix556.json
docs/lineage_verified/fix553.json docs/lineage_verified/fix554.json
firered/baseline.json firered/patches/recap_boxes.s firered/recap_species_range.py
leafgreen/baseline.json leafgreen/patches/recap_boxes.s
leafgreen/experiments/first_glyph.py
leafgreen/rebuild_1_0_tail.py
leafgreen/rebuild_merge561.py
leafgreen/rebuild_557_559.py tests/test_manifest_replay.py
leafgreen/rebuild_layout555_556.py tests/test_layout_replay.py
leafgreen/rebuild_revisions553.py tests/test_revisions553.py
shared/frlg/__init__.py shared/frlg/rom.py shared/frlg/text.py shared/frlg/events.py shared/frlg/script.py
shared/frlg/encode.py shared/frlg/font_pages.py shared/frlg/glyph_codec.py
shared/frlg/lineage.py shared/frlg/lz77.py
shared/frlg/merge.py
tests/test_core.py tests/test_publication.py tools/check_publication.py tools/inspect_rom.py
tests/test_leafgreen_origin.py
tests/test_lineage.py tools/audit_build_lineage.py
""".split())
IGNORED = {".git", "build", "__pycache__"}
PATTERNS = {
    "private home path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    "Windows home path": re.compile(r"[A-Z]:\\Users\\[^\\]+\\"),
    "GitHub token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access id": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "private email": re.compile(r"[\w.+-]+@(?:gmail|qq|163|126|outlook|hotmail)\.[A-Za-z]+", re.I),
}


def inspect(root: Path) -> tuple[list[str], list[str]]:
    found, errors = [], []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in IGNORED for part in rel.parts):
            continue
        if path.is_symlink():
            errors.append(f"symlink forbidden: {rel}")
            continue
        if not path.is_file():
            continue
        name = rel.as_posix()
        found.append(name)
        if name not in ALLOWED:
            errors.append(f"not allowlisted: {name}")
        raw = path.read_bytes()
        if len(raw) > 100_000 or b"\x00" in raw:
            errors.append(f"binary or oversized file: {name}")
            continue
        try:
            body = raw.decode("utf8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF8 file: {name}")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(body):
                errors.append(f"{label}: {name}")
    errors.extend(f"missing required file: {p}" for p in sorted(ALLOWED - set(found)))
    return found, errors


def main():
    found, errors = inspect(ROOT)
    print(json.dumps(dict(status="FAIL" if errors else "PASS", file_count=len(found),
                          files=found, errors=errors), ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
