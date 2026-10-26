.syntax unified
.cpu arm7tdmi
.thumb
.balign 4
.global gate
.thumb_func
gate:
    ldr r3, [r6]
    ldr r2, =0x086D9048
    cmp r3, r2
    blo main
    ldr r2, =0x086D9054
    cmp r3, r2
    blo small
    ldr r2, =0x086D9066
    cmp r3, r2
    bhs main
    ldrb r2, [r6, #5]
    cmp r2, #0
    bne main
    ldr r2, =0x03003134
    ldr r2, [r2]
    ldr r3, =0x0812F319
    cmp r2, r3
    bne main
small:
    movs r1, #0
    ldr r3, =0x089D13E1
    bx r3
main:
    @ Current releases forward to a later font-tier gate, not directly to main.
    ldr r3, =MAIN_FONT_ROUTE
    bx r3
.balign 4
.ltorg
