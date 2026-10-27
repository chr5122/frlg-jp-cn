.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global decode_gate,slot_align,payload_end

decode_gate:
 push {r0,r1,r4,lr}
 @ FC06 switches the active font without changing template.fontId.
 ldrb r1,[r6,#20]
 movs r0,#15
 ands r1,r0
 cmp r1,#0
 bne fallback
 ldr r0,[r6]
 ldr r1,=SLOT_START
 cmp r0,r1
 blo check_units
 ldr r1,=SLOT_END
 cmp r0,r1
 blo small
check_units:
 ldr r1,=units
next_unit:
 ldmia r1!,{r2,r3}
 cmp r2,#0
 beq fallback
 cmp r0,r2
 bne next_unit
 ldr r4,[sp]
 cmp r4,r3
 bne fallback
small:
 pop {r0,r1}
 movs r1,#0
 bl small_decoder
 pop {r4}
 pop {r3}
 mov lr,r3
 ldr r3,=0x08005B2B
 bx r3
fallback:
 pop {r0,r1,r4}
 pop {r3}
 mov lr,r3
 ldr r3,=OLD_GATE
 bx r3
small_decoder:
 ldr r3,=0x089D1401
 bx r3
.ltorg
.balign 4
units:
.word 0x08b2d41b,0x3bc
.word 0x08b2d43b,0x3bc
.word 0x08b2d45b,0x3bc
.word 0x08b2d6bd,0x4b7
.word 0x08b2d6c6,0x3bc
.word 0x08b2d6d0,0x4b7
.word 0x08b2d6d9,0x3bc
.word 0,0
@ Original slot controls consumer only. Measure from the same small table
@ and native icon widths, then restore ABI and resume after the old bypass.
slot_align:
 push {r0,r1,r4,lr}
 movs r0,r4
 bl measure
 movs r2,#0
 cmp r0,#236
 bhi aligned
 movs r2,#236
 subs r2,r2,r0
aligned:
 pop {r0,r1,r4}
 pop {r3}
 mov lr,r3
 ldr r3,=0x08141A35
 bx r3
measure:
 ldr r3,=0x086D5049
 bx r3
.ltorg
payload_end:
