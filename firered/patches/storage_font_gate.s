.syntax unified
.cpu arm7tdmi
.thumb
.text
.global pc_font_gate48
.thumb_func

pc_font_gate48:
 push {r0,r1,r2,r3,r4,lr}
 ldrb r1,[r6,#5]
 cmp r1,#2
 bne pc_fallback48
 ldrb r1,[r6,#20]
 movs r0,#15
 ands r1,r0
 cmp r1,#2
 bne pc_fallback48
 ldr r4,=0x020396fc
 ldr r4,[r4]
 ldr r0,=0x02000000
 cmp r4,r0
 blo pc_fallback48
 ldr r0,=0x02037000
 cmp r4,r0
 bhi pc_fallback48
 ldr r0,[r6]
 ldr r1,=0xcf5
 adds r1,r4,r1
 cmp r0,r1
 blo pc_fallback48
 adds r1,#72
 cmp r0,r1
 bhs pc_fallback48
 subs r1,#72
 movs r2,r1
 adds r2,#36
 cmp r0,r2
 blo pc_count_init48
 movs r1,r2
 adds r1,#1
pc_count_init48:
 ldrb r0,[r1]
 cmp r0,#247
 bne pc_fallback48
 movs r0,#0
 movs r2,#0
pc_count48:
 cmp r2,#16
 bhs pc_fallback48
 ldrb r3,[r1,r2]
 cmp r3,#255
 beq pc_count_done48
 cmp r3,#247
 bne pc_native48
 adds r0,#1
 adds r2,#3
 b pc_count48
pc_native48:
 adds r0,#1
 adds r2,#1
 b pc_count48
pc_count_done48:
 cmp r0,#5
 bne pc_fallback48
 pop {r0,r1,r2,r3}
 movs r1,#0
 ldr r4,=0x089d13e1
 bl call_r4_48
 pop {r4}
 pop {r3}
 bx r3
pc_fallback48:
 pop {r0,r1,r2,r3,r4}
 pop {r3}
 mov lr,r3
 ldr r3,=OLD_FONT_GATE48
 bx r3
.thumb_func
call_r4_48:
 bx r4
@ Four earlier-wrapper literals retained to preserve current PC-relative layout.
.word 0x08FF81B3,0x0809350D,0x08FF8281,0x0808F6B9
.ltorg
