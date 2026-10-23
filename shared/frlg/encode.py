#!/usr/bin/env python3
"""Strict UTF-8/text-token -> BPGJ private-CN byte encoder.

The input is ordinary Unicode plus explicit {TOKENS}; no control byte is ever
accepted as literal text. Private IDs use F7 + big-endian u16; existing
F7 00 <id> streams remain byte-for-byte unchanged. The encoder rejects an
unallocated character or token instead of substituting a Japanese glyph.
"""
from __future__ import annotations
import argparse, csv, re, sys
from pathlib import Path

from .font_pages import MAX_GID as CN_MAX_GID   # FIX348：ID 上限唯一真源（页 00..0A）

PREFIX = b'\xF7'
TOKENS = {
    'NL': b'\xFE', 'PAGE': b'\xFB', 'END': b'\xFF',
    'WAIT': b'\xFA',
    # Existing Gen III placeholder syntax: this inserts a native BPGJ string;
    # it does not re-encode the name stored in the save file.
    'PLAYER': b'\xFD\x01', 'STR_VAR_1': b'\xFD\x02',
    'STR_VAR_2': b'\xFD\x03', 'STR_VAR_3': b'\xFD\x04',
    'RIVAL': b'\xFD\x06',
    # BPGJ extended control code: change the renderer's glyph branch for the
    # remainder of this string. This changes neither save strings nor data.
    'FONT_NORMAL': b'\xFC\x06\x02',
    'FONT_MALE': b'\xFC\x06\x04',
    # Verified BPGJ battle-window controls.  These retain the original action
    # menu palette/highlight setup and its two-column geometry while the
    # labels themselves use the private Chinese encoding.
    'BATTLE_STYLE': b'\xFC\x05\x05\xFC\x04\x0D\x0E\x0F',
    # BPGJ's Japanese action menu aligns its right column with full-width
    # native spaces.  Chinese labels have fewer 16px glyphs than their JP
    # counterparts, so each row needs its own explicit padding to preserve
    # the original right-column anchor (not a guessed renderer offset).
    'BATTLE_COLUMN_AFTER_2': b'\x00\x00\x00\x00',
    'BATTLE_COLUMN_AFTER_3': b'\x00\x00\x00',
    # Native BPGJ Latin glyphs used for controller labels; these never enter
    # the private Chinese encoding space.
    'L': b'\xC6', 'R': b'\xCC',
    # BPGJ extended control: pause until a button press (FC 09), used by PC
    # menu messages such as the empty-mailbox notice before their FF terminator.
    'PAUSE_PRESS': b'\xFC\x09',
    # BPGJ extended control: pause for 60 frames (FC 08 3C), used by battle
    # strings such as the trainer send-out message.
    'PAUSE_60': b'\xFC\x08\x3C',
    # BPGJ battle-string variables (BattleStringExpandPlaceholders operands).
    # Distinct names avoid colliding with the field-text FD tokens above.
    'B_BUFF1': b'\xFD\x00',
    'B_BUFF2': b'\xFD\x01',
    'B_BUFF3': b'\xFD\x30',
    'B_PLAYER_MON': b'\xFD\x05',
    'B_PLAYER_MON2': b'\xFD\x07',
    'B_OPPONENT_MON': b'\xFD\x06',
    'B_OPPONENT_MON2': b'\xFD\x08',
    'B_LINK_PLAYER_MON1': b'\xFD\x09',
    'B_LINK_OPPONENT_MON1': b'\xFD\x0A',
    'B_LINK_PLAYER_MON2': b'\xFD\x0B',
    'B_LINK_OPPONENT_MON2': b'\xFD\x0C',
    'B_TRAINER_CLASS': b'\xFD\x1C',
    'B_TRAINER_NAME': b'\xFD\x1D',
    'B_PLAYER_NAME': b'\xFD\x23',
    'B_ATK_NAME': b'\xFD\x0F',
    'B_DEF_NAME': b'\xFD\x10',
    'B_EFF_NAME': b'\xFD\x11',
    'B_ACTIVE_NAME': b'\xFD\x12',
    'B_SCR_ACTIVE_NAME': b'\xFD\x13',
    'B_CURRENT_MOVE': b'\xFD\x14',
    'B_LAST_ITEM': b'\xFD\x16',
    'B_ATK_ABILITY': b'\xFD\x18',
    'B_DEF_ABILITY': b'\xFD\x19',
    'B_SCR_ACTIVE_ABILITY': b'\xFD\x1A',
    'B_EFF_ABILITY': b'\xFD\x1B',
    'B_TRAINER1_LOSE': b'\xFD\x24',
    'B_PC_CREATOR_NAME': b'\xFD\x27',
    'B_ATK_PREFIX1': b'\xFD\x28',
    'B_DEF_PREFIX1': b'\xFD\x29',
    'B_ATK_PREFIX2': b'\xFD\x2A',
    'B_ATK_PREFIX3': b'\xFD\x2C',
    'B_LINK_PARTNER_NAME': b'\xFD\x1F',
    'B_LINK_OPPONENT1_NAME': b'\xFD\x20',
    'B_LINK_OPPONENT2_NAME': b'\xFD\x21',
    'B_LINK_SCR_TRAINER_NAME': b'\xFD\x22',
}
# Explicit BPGJ-native characters.  Modern US-CN's punctuation streams use
# native one-byte punctuation too; importing those bytes as a private 16×16
# glyph was the cause of malformed `。` / `？` / `：` at runtime.  Keep these
# in the original text-printer path.  `：` uses BPGJ's documented stable
# Latin-colon character (`F0`), rather than a fake ellipsis substitution.
#
# BPGJ has no suitable full-width Chinese comma in this native byte range:
# B8 is an English-layout slot, and visibly renders incorrectly in the JP
# text path. Keep the verified modern-US-CN 64-byte comma in the private
# bank instead (stable glyph ID 0x0049).
# Existing private glyph IDs remain allocated in the charmap for historical
# compatibility, but new UTF-8 resources encode these characters natively.
NATIVE = {
    ' ': 0x00,
    '!': 0xAB,   # ASCII exclamation shares BPGJ's 0xAB glyph (US-CN "Go!" keeps ASCII '!')
    '！': 0xAB,
    '-': 0xAE,   # BPGJ hyphen (also the long-vowel mark glyph); used by MOVE_NONE
    'ー': 0xAE,
    '？': 0xAC,
    '。': 0xAD,
    '：': 0xF0,
    ',': 0xB8,
    '¥': 0xB7,   # BPGJ yen glyph; used by battle prize-money strings
    '…': 0xB0,   # BPGJ ellipsis; US-CN battle streams use the same byte
    # BPGJ native Latin glyphs used by fixed texts (digits 0-9, A-Z).
    # These never enter the private Chinese encoding space; {L}/{R} remain
    # explicit tokens for controller labels.
    '0': 0xA1, '1': 0xA2, '2': 0xA3, '3': 0xA4, '4': 0xA5,
    '5': 0xA6, '6': 0xA7, '7': 0xA8, '8': 0xA9, '9': 0xAA,
    'A': 0xBB, 'B': 0xBC, 'C': 0xBD, 'D': 0xBE, 'E': 0xBF,
    'F': 0xC0, 'G': 0xC1, 'H': 0xC2, 'I': 0xC3, 'J': 0xC4,
    'K': 0xC5, 'L': 0xC6, 'M': 0xC7, 'N': 0xC8, 'O': 0xC9,
    'P': 0xCA, 'Q': 0xCB, 'R': 0xCC, 'S': 0xCD, 'T': 0xCE,
    'U': 0xCF, 'V': 0xD0, 'W': 0xD1, 'X': 0xD2, 'Y': 0xD3,
    'Z': 0xD4,
    'a': 0xD5, 'b': 0xD6, 'c': 0xD7, 'd': 0xD8, 'e': 0xD9,
    'f': 0xDA, 'g': 0xDB, 'h': 0xDC, 'i': 0xDD, 'j': 0xDE,
    'k': 0xDF, 'l': 0xE0, 'm': 0xE1, 'n': 0xE2, 'o': 0xE3,
    'p': 0xE4, 'q': 0xE5, 'r': 0xE6, 's': 0xE7, 't': 0xE8,
    'u': 0xE9, 'v': 0xEA, 'w': 0xEB, 'x': 0xEC, 'y': 0xED,
    'z': 0xEE,
}
TOKEN_RE = re.compile(r'\{([^{}]+)\}')

class EncodeError(ValueError): pass

def glyph_characters(text: str) -> list[str]:
    """Return literal text characters only, excluding explicit `{TOKENS}`.

    The allocator uses this to decide which private glyphs must be copied;
    token spelling (notably the L/R in `{PLAYER}`) must never allocate a
    glyph or affect a strict real-source audit.
    """
    out=[]; pos=0
    while pos<len(text):
        if text[pos]=='{':
            m=TOKEN_RE.match(text,pos)
            if not m: raise EncodeError(f'incomplete token at character {pos}')
            if m.group(1).startswith('RAW:'):
                raise EncodeError('RAW bypass is disabled in the public encoder')
            if m.group(1) not in TOKENS: raise EncodeError(f'unrecognized token {{{m.group(1)}}}')
            pos=m.end();continue
        if text[pos]=='}': raise EncodeError(f'unmatched }} at character {pos}')
        out.append(text[pos]);pos+=1
    return out

def load_charmap(path: Path) -> dict[str, dict]:
    result = {}; owners = {}
    with path.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            ch = row['unicode']
            if not ch or row['status'] not in {'verified', 'allocated'}:
                continue
            gid = int(row['glyph_id'], 0)
            if not 0 <= gid <= CN_MAX_GID: raise EncodeError(f'{ch}: glyph ID outside declared private-bank range (max 0x{CN_MAX_GID:04X})')
            if len(ch) != 1 or ord(ch) < 32 or ord(ch) == 127:
                raise EncodeError('one printable Unicode character required per row')
            if ch in result: raise EncodeError(f'duplicate Unicode allocation: {ch}')
            if gid in owners: raise EncodeError(f'duplicate private glyph ID {gid:#x}')
            owners[gid] = ch
            result[ch] = row | {'_gid': gid}
    return result

def encode(text: str, charmap: dict[str, dict], *, require_end=True) -> bytes:
    out = bytearray(); pos = 0; ended = False
    while pos < len(text):
        if text[pos] == '{':
            m = TOKEN_RE.match(text, pos)
            if not m: raise EncodeError(f'incomplete token at character {pos}')
            token = m.group(1)
            if token.startswith('RAW:'):
                raise EncodeError('RAW bypass is disabled in the public encoder; use explicit verified tokens')
            if token not in TOKENS: raise EncodeError(f'unrecognized token {{{token}}}')
            if ended: raise EncodeError('text follows {END}')
            out += TOKENS[token]; ended = token == 'END'; pos = m.end(); continue
        ch = text[pos]
        if ch == '}': raise EncodeError(f'unmatched }} at character {pos}')
        if ended: raise EncodeError('text follows {END}')
        if ord(ch) < 32 or ord(ch) == 127:
            raise EncodeError('literal control characters require explicit tokens')
        if ch in NATIVE: out.append(NATIVE[ch])
        elif ch in charmap:
            gid = charmap[ch]['_gid']
            if type(gid) is not int or not 0 <= gid <= CN_MAX_GID:
                raise EncodeError('private glyph ID outside declared range')
            out += PREFIX + gid.to_bytes(2,'big')
        else: raise EncodeError(f'unknown Unicode character {ch!r} at character {pos}')
        pos += 1
    if require_end and not ended: out += TOKENS['END']
    if out:
        from .text import exact
        # Validate token structure even when a caller supplied a hand-made map.
        candidate = bytes(out) if ended or require_end else bytes(out) + TOKENS['END']
        stream = exact(candidate, 'cn')
        if stream.status != 'OK':
            raise EncodeError(f'encoded stream rejected: {stream.status}')
    return bytes(out)

def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--charmap',required=True,type=Path);ap.add_argument('--text',required=True);ap.add_argument('--hex',action='store_true')
    ns=ap.parse_args(); result=encode(ns.text,load_charmap(ns.charmap))
    print(result.hex(' ') if ns.hex else result)
if __name__ == '__main__': main()
