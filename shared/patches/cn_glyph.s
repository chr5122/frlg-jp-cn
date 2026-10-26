.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global cn_decode_glyph
.type cn_decode_glyph, %function
.thumb_func

@ Project-owned parameterized extraction of the four-tile decoder algorithm.
@ This is a CALLABLE CORE, not a RenderText hook or original-ROM installer.
@ r0: unsigned private glyph ID; r1: pointer to six aligned u32 fields:
@   +0 page-pointer table, +4 page count, +8 blank 0x4000-byte page,
@   +12 writable 0x80-byte glyph scratch, +16 writable two-byte metrics,
@   +20 native DecompressGlyphTile Thumb function pointer.
@ Each real page spans 0x4000 bytes; holes must point to the blank page.
@ Decode all four tiles, report 12x12; never infer read/write from LR.
@ Caller validates config, lifetimes, page count, pointers and register ABI.
cn_decode_glyph:
    push {r4-r7, lr}
    sub sp, #4                  @ preserve public-interface stack alignment
    movs r7, r1
    movs r4, r0
    lsrs r2, r0, #8
    ldr r3, [r7, #4]
    cmp r2, r3
    bhs blank_page
    lsls r2, r2, #2
    ldr r3, [r7]
    ldr r5, [r3, r2]
    b glyph_offset
blank_page:
    ldr r5, [r7, #8]
glyph_offset:
    movs r3, #255
    ands r4, r3
    lsrs r2, r4, #3
    lsls r2, r2, #9
    movs r3, #7
    ands r4, r3
    lsls r4, r4, #5
    adds r4, r4, r2
    adds r4, r4, r5
    ldr r6, [r7, #12]
    movs r0, r4
    movs r1, r6
    bl call_tile
    adds r0, r4, #0
    adds r0, #16
    adds r1, r6, #0
    adds r1, #32
    bl call_tile
    movs r5, #128
    lsls r5, r5, #1
    adds r0, r4, r5
    adds r1, r6, #0
    adds r1, #64
    bl call_tile
    adds r5, #16
    adds r0, r4, r5
    adds r1, r6, #0
    adds r1, #96
    bl call_tile
    ldr r1, [r7, #16]
    movs r0, #12
    strb r0, [r1]
    strb r0, [r1, #1]
    add sp, #4
    pop {r4-r7, pc}
call_tile:
    ldr r3, [r7, #20]
    bx r3
.size cn_decode_glyph, .-cn_decode_glyph
