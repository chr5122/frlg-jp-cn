.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.balign 4
.global cn_main_entry, cn_main_draw

@ Current production layout, not the parameterized experimental cn_glyph core.
@ Link with explicit per-game PREFIX_ROUTE/METRICS and font-page constants.
@ Preserve the historical +4 template byte load: it is windowId, NOT fontId.
@ The normal four-tile decoder does not use that byte to choose a font tier.
.thumb_func
cn_main_entry:
    cmp r3, #0xf7
    bne native_char
    ldrb r1, [r6, #4]
    ldr r3, [r6]
    ldrb r0, [r3]
    ldrb r2, [r3, #1]
    adds r3, #2
    str r3, [r6]
    lsls r0, r0, #8
    orrs r0, r2
.ifdef PREFIX_USES_BX
    ldr r3, [pc, #0]
    bx r3
    .word PREFIX_ROUTE + 1
.else
    bl PREFIX_ROUTE
    ldr r0, return_to_window
    bx r0
.endif
native_char:
    movs r0, r3
    subs r0, #0xf8
    bx lr
.thumb_func
cn_main_draw:
    push {r4-r7, lr}
    movs r4, r0
    movs r7, r0
    lsrs r7, r7, #8
    cmp r7, #CN_FONT_MAX_PAGE
    bhi blank_page
    lsls r7, r7, #2
    ldr r5, page_table
    ldr r5, [r5, r7]
    b page_offset
    nop
    nop
    nop
blank_page:
    ldr r5, blank_pointer
    b page_offset
    nop
    nop
page_offset:
    movs r7, #255
    ands r4, r7
    lsrs r7, r4, #3
    lsls r7, r7, #9
    movs r4, #7
    ands r4, r0
    lsls r4, r4, #5
    adds r4, r4, r7
    adds r4, r4, r5
    ldr r6, glyph_scratch
    movs r0, r4
    movs r1, r6
    bl call_tile
    movs r7, #16
    adds r0, r4, r7
    movs r7, #32
    adds r1, r6, r7
    bl call_tile
    ldr r7, lower_left
    adds r0, r4, r7
    movs r7, #64
    adds r1, r6, r7
    bl call_tile
    ldr r7, lower_right
    adds r0, r4, r7
    movs r7, #96
    adds r1, r6, r7
    bl call_tile
    bl MAIN_METRICS
    strb r0, [r1]
    movs r0, #13
    strb r0, [r1, #1]
    pop {r4-r7, pc}
@ Retained production labels/layout, not a promise to use these for small CJK.
small_layout:
    movs r0, r4
    movs r1, r6
    bl call_tile
    ldr r7, lower_left
    adds r0, r4, r7
    movs r7, #64
    adds r1, r6, r7
    bl call_tile
    ldr r1, glyph_metrics
    movs r0, #8
    strb r0, [r1]
    movs r0, #12
    strb r0, [r1, #1]
    pop {r4-r7, pc}
copy1_layout:
    movs r0, r4
    movs r1, r6
    bl call_tile
    ldr r7, lower_left
    adds r0, r4, r7
    movs r7, #64
    adds r1, r6, r7
    bl call_tile
    ldr r1, glyph_metrics
    movs r0, #8
    strb r0, [r1]
    movs r0, #16
    strb r0, [r1, #1]
    pop {r4-r7, pc}
call_tile:
    ldr r3, tile_function
    bx r3
.balign 4
return_to_window: .word 0x08005B2B
page_table: .word CN_FONT_PAGE_TABLE
blank_pointer: .word CN_FONT_BLANK_PAGE
glyph_scratch: .word 0x03003DE0
lower_left: .word 0x100
lower_right: .word 0x110
glyph_metrics: .word 0x03003E60
tile_function: .word 0x08002F5D
