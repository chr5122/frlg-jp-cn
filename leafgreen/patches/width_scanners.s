.syntax unified
.cpu arm7tdmi
.thumb
.section .text
@ Frozen current implementation. The variable native fallback0x08005E29
@ lands in dispatch-table data. This source match is NOT a safety endorsement.

.ifdef SMALL_FULL10
.set CN_ANY_FULL10, 1
.endif
.ifdef COPY1_FULL10
.set CN_ANY_FULL10, 1
.endif

@ FIX348：私用 ID 上限的唯一真源在 scripts/cn_font_pages.py（CN_FONT_MAX_GID）。
@ 定宽与变宽两个入口共用下面这一个字面量，改一处两处同时生效。
.ifndef CN_FONT_MAX_GID
.set CN_FONT_MAX_GID, 0x0AFF       @ 页 0x00..0x0A：0x0000..0x0AFF
.endif

@ Compatibility for the project's F7 + big-endian u16 Chinese glyph IDs.
@
@ Scope is deliberately narrow:
@   * PC message variables: 0x02021C00..0x02021DFF
@   * Bag list strings: allocation whose base pointer lives at 0x0203AC94,
@     with 43 expanded rows x 32 bytes = 0x560 bytes.
@   * Summary-screen Chinese move labels: tail slots appended to the active
@     `sMonSummaryScreen` allocation, reached through BPGJ's verified pointer
@     at 0x0203B0B4.  The five 16-byte slots begin at +0x32B4.
@   * The external 16-byte Chinese move-name table at 0x08B2E000..0x08B2F630.
@   * relocated field/menu text: 0x08B10000..0x08B2DFFF
@   * private item-description strings: 0x08BC0A40..0x08BFFFFF
@   * private Pokédex species/category streams: 0x08DA1000..0x08DA7FFF and
@     0x08DA9000..0x08DB7FFF (the gap contains non-text pointer data)
@
@ Every other native BPGJ F7 control sequence remains on BPGJ's original
@ two-byte handler.  In particular, this is not a global F7 reinterpretation.

.global cn_pc_bag_f7_fixedwidth_hook
.global cn_pc_bag_f7_variablewidth_hook

@ Input at the native fixed-width F7 dispatch point:
@   r4 = string base, r2 = current byte index, r5 = glyph count.
cn_pc_bag_f7_fixedwidth_hook:
.ifdef PROBE
    ldr r0, =0x0203FFEC
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    ldr r0, =0x0203FFF4
    str r3, [r0]
.endif
    push {r3, lr}
    adds r3, r4, r2
    bl cn_pc_bag_is_private_ptr
    adds r1, r0, #0
    pop {r3}
    pop {r0}
    mov lr, r0
    adds r0, r1, #0
    cmp r0, #0
    beq cn_pc_bag_fixed_native
    movs r0, r2
    ldrb r0, [r4, r0]
    movs r1, r2
    adds r1, #1
    ldrb r1, [r4, r1]
    lsls r0, r0, #8
    orrs r0, r1
    @ Private IDs are page 0 plus pages 1..0x0A. Keep this aligned with
    @ scripts/cn_font_pages.py and mvp08_chinese_hook.s: the accepted range is
    @ 0x0000..CN_FONT_MAX_GID. The pointer ownership guard above keeps native
    @ BPGJ F7 controls on their own path.
    ldr r1, =CN_FONT_MAX_GID
    cmp r0, r1
    bhi cn_pc_bag_fixed_native
    adds r2, #2
    adds r5, #1
    ldr r0, =0x08005D59
    bx r0
cn_pc_bag_fixed_native:
    ldr r0, =0x08005D4D
    bx r0

@ Input at the native variable-width F7 dispatch point:
@   r4 points at F7, r8 accumulates width.
cn_pc_bag_f7_variablewidth_hook:
.ifdef PROBE
    ldr r0, =0x0203FFF0
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    ldr r0, =0x0203FFF8
    str r4, [r0]
.endif
    push {r3, lr}
    adds r3, r4, #0
    bl cn_pc_bag_is_private_ptr
    adds r1, r0, #0
    pop {r3}
    pop {r0}
    mov lr, r0
    adds r0, r1, #0
    cmp r0, #0
    beq cn_pc_bag_variable_native
    ldrb r0, [r4, #1]
    ldrb r1, [r4, #2]
    lsls r0, r0, #8
    orrs r0, r1
    @ See fixed-width path: private ID range is 0x0000..CN_FONT_MAX_GID.
    ldr r1, =CN_FONT_MAX_GID
    cmp r0, r1
    bhi cn_pc_bag_variable_native
.ifdef PRIVATE_FULL12
    @ Imported Chinese glyphs have live pixels in columns 0..11.  A 10- or
    @ 11-pixel metric clips real right-edge strokes, so the complete private
    @ glyph contract is 12 pixels wide.
    bl width_alias
.endif
    @ GetStringWidth carries the active font id in r7.  BPGJ's small and
    @ normal-copy-1 fonts are 8 pixels wide; the normal/copy-2/male/female
    @ branches use the 10-pixel private glyph layout.
.ifdef SMALL_FULL10
    @ Diagnostic/repair variant: the shared Chinese source is a 16x16
    @ four-tile glyph.  FONT_SMALL must use that complete source as well;
    @ taking only its left 8 columns produces the reported narrow glyphs.
    cmp r7, #0
    beq cn_pc_bag_width_full10
.endif
    cmp r7, #0
    beq cn_pc_bag_width_small
.ifdef COPY1_FULL10
    cmp r7, #1
    beq cn_pc_bag_width_full10
.else
    cmp r7, #1
    beq cn_pc_bag_width_small
.endif
    movs r0, #10
    b cn_pc_bag_add_width
cn_pc_bag_width_small:
    movs r0, #8
cn_pc_bag_add_width:
    add r8, r0
    adds r4, #2
    ldr r0, =0x08005F6D
    bx r0
.ifdef CN_ANY_FULL10
cn_pc_bag_width_full10:
    movs r0, #10
    b cn_pc_bag_add_width
.endif
cn_pc_bag_variable_native:
    ldr r0, =0x08005E29
    bx r0

@ r3 = current F7 address. Returns r0=1 only for a known private-text buffer.
cn_pc_bag_is_private_ptr:
    ldr r0, =0x02021C00
    cmp r3, r0
    blo cn_pc_bag_try_bag
    ldr r0, =0x02021DFF
    cmp r3, r0
    bls cn_pc_bag_yes
cn_pc_bag_try_summary:
    @ Pokemon summary's move labels are heap fields, so their base changes
    @ between summary-screen entries.  Read the owning allocation pointer
    @ instead of widening this compatibility hook to all EWRAM strings.
    ldr r0, =0x0203B0B4
    ldr r0, [r0]
    cmp r0, #0
    beq cn_pc_bag_try_desc
    ldr r1, =0x32B4
    adds r0, r0, r1
    cmp r3, r0
    blo cn_pc_bag_try_desc
    ldr r1, =0x50           @ 5 widened move-name slots * 16 bytes
    adds r0, r0, r1
    cmp r3, r0
    blo cn_pc_bag_yes
cn_pc_bag_try_desc:
    @ Ordinary relocated UTF-8 field/menu resources use the same private
    @ F7+u16 stream, but live outside the narrower item-description window.
    @ This includes START-menu descriptions at 0x08B13288.
    ldr r0, =0x08B10000
    cmp r3, r0
    blo cn_pc_bag_try_desc_legacy
    ldr r0, =0x08B2E000
    cmp r3, r0
    blo cn_pc_bag_yes

    @ Summary pages now print long move names directly from this immutable
    @ external table.  Its streams are F7 + BE-u16, so they must use the
    @ private 3-byte measurement path rather than BPGJ's native 2-byte F7.
    ldr r0, =0x08B2E000
    cmp r3, r0
    blo cn_pc_bag_try_desc_legacy
    ldr r0, =0x08B2F630
    cmp r3, r0
    blo cn_pc_bag_yes
cn_pc_bag_try_desc_legacy:
    @ External item descriptions are immutable ROM strings, not gStringVar
    @ buffers. They are deliberately bounded to the allocator's declared
    @ description range so native F7 strings elsewhere remain native.
    ldr r0, =0x08BC0A40
    cmp r3, r0
    blo cn_pc_bag_try_bag
    ldr r0, =0x08C00000
    cmp r3, r0
    blo cn_pc_bag_yes
cn_pc_bag_try_bag:
    @ Pokédex lists and details print immutable F7+u16 streams directly from
    @ their private ROM windows.  Keep the two text windows exact so native
    @ BPGJ F7 controls in the intervening ROM data retain their original
    @ two-byte interpretation.
    ldr r0, =0x08DA1000
    cmp r3, r0
    blo cn_pc_bag_try_bag_heap
    ldr r1, =0x08DB8000
    cmp r3, r1
    bhs cn_pc_bag_try_bag_heap
    ldr r0, =0x08DA8000
    cmp r3, r0
    blo cn_pc_bag_yes
    ldr r0, =0x08DA9000
    cmp r3, r0
    bhs cn_pc_bag_yes
cn_pc_bag_try_bag_heap:
    ldr r0, =0x0203AC94
    ldr r0, [r0]
    cmp r0, #0
    beq cn_pc_bag_no
    cmp r3, r0
    blo cn_pc_bag_no
    ldr r1, =0x560
    adds r0, r0, r1
    cmp r3, r0
    blo cn_pc_bag_yes
cn_pc_bag_no:
    movs r0, #0
    bx lr
cn_pc_bag_yes:
    movs r0, #1
    bx lr

.ltorg
@ Current width aliases; fixed production patch, not font bitmap data.
width_alias:
 ldr r1, =0x092F
 cmp r0, r1
 bne alias_bounds
 movs r0, #0
 b alias_done
alias_bounds:
 ldr r1, =0x092A
 cmp r0, r1
 blo alias_ordinary
 ldr r1, =0x092E
 cmp r0, r1
 bhi alias_ordinary
 movs r0, #10
 b alias_done
alias_ordinary:
 movs r0, #12
alias_done:
 ldr r1, =0x08BC0071
 bx r1
.ltorg
