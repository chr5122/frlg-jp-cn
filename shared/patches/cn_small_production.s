.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global cn_small_decode

@ Production small-glyph decoder extracted from the owned Help implementation.
@ r0=private ID, r1=0 for small; other inputs fall back to the main drawer.
@ Page slots are CONTIGUOUS 64B, unlike the main banked source codec.
.thumb_func
cn_small_decode:
    cmp r1, #0
    bne original_decode
    ldr r2, =CN_FONT_MAX_GID
    cmp r0, r2
    bhi original_decode
    push {r4-r7, lr}
    movs r7, r0
    lsrs r2, r0, #8
    lsls r2, r2, #2
    ldr r3, =SMALL_PAGES
    ldr r4, [r3, r2]
    movs r2, #255
    ands r0, r2
    lsls r0, r0, #6
    adds r4, r4, r0
    ldr r5, =0x03003DE0
    movs r6, #0
tile_loop:
    movs r0, r4
    movs r1, r5
    bl tile_decode
    adds r4, #16
    adds r5, #32
    adds r6, #1
    cmp r6, #4
    bne tile_loop
    ldr r1, =SMALL_WIDTHS
    ldrb r0, [r1, r7]
    ldr r1, =0x03003E60
    strb r0, [r1]
    movs r0, #13
    strb r0, [r1, #1]
    pop {r4-r7}
    pop {r0}
    bx r0
original_decode:
    ldr r3, =MAIN_DRAW
    bx r3
tile_decode:
    ldr r3, =0x08002F5D
    bx r3
.ltorg
