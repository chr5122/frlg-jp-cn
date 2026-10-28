.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global measure
.thumb_func
measure:
    push {r4-r7,lr}
    movs r4, r0
    movs r5, #0
    movs r6, #0
next_token:
    ldrb r0, [r4]
    adds r4, #1
    cmp r0, #255
    beq measured
    cmp r0, #247
    beq glyph
    cmp r0, #248
    beq icon
    cmp r0, #252
    beq shift
    movs r7, r0
    bl native_small
    ldr r0, =0x03003E60
    ldrb r0, [r0]
    adds r5, r5, r0
    cmp r7, #0
    beq next_token
    movs r6, r5
    b next_token
glyph:
    ldrb r0, [r4]
    ldrb r1, [r4,#1]
    adds r4, #2
    lsls r0, r0, #8
    orrs r0, r1
    ldr r1, =SMALL_WIDTHS
    ldrb r0, [r1,r0]
    b add_content
icon:
    ldrb r0, [r4]
    adds r4, #1
    bl icon_width
add_content:
    adds r5, r5, r0
    movs r6, r5
    b next_token
shift:
    adds r4, #1
    ldrb r5, [r4]
    adds r4, #1
    b next_token
measured:
    movs r0, r6
    pop {r4-r7}
    pop {r1}
    bx r1
native_small:
    ldr r3, =0x080062B5
    bx r3
icon_width:
    ldr r3, =0x08006295
    bx r3
.ltorg

