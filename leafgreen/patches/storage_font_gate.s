.syntax unified
.cpu arm7tdmi
.thumb
.section .text.font,"ax"
.global storage_font_gate
storage_font_gate:
 push {r0,r1,r2,r3,r4,lr}
 movs r4,r6
 adds r4,#20
 ldrb r1,[r4]
 movs r0,#15
 ands r1,r0
 cmp r1,#2
 bne fallback
 ldr r4,=0x020396FC
 ldr r4,[r4]
 ldr r0,=0x02000000
 cmp r4,r0
 blo fallback
 ldr r0,=0x02037000
 cmp r4,r0
 bhi fallback
 ldr r0,[r6]
 ldr r1,=0xCF5
 adds r1,r4,r1
 cmp r0,r1
 blo fallback
 adds r1,#72
 cmp r0,r1
 bhs fallback
 /* Count visible tokens in the owning UI string, not raw byte length.
  * 1--4 glyphs keep the normal font. Only five-glyph names shrink.
  * First string starts CF5; second retains its native slash at D19. */
 subs r1,#72
 movs r2,r1
 adds r2,#36
 cmp r0,r2
 blo count_init
 movs r1,r2
 adds r1,#1
count_init:
 movs r0,#0
 movs r2,#0
count_loop:
 cmp r2,#16
 bhs fallback
 ldrb r3,[r1,r2]
 cmp r3,#255
 beq count_done
 cmp r3,#247
 bne native_token
 adds r0,#1
 adds r2,#3
 b count_loop
native_token:
 adds r0,#1
 adds r2,#1
 b count_loop
count_done:
 cmp r0,#5
 bne fallback
 pop {r0,r1,r2,r3}
 movs r1,#0
 bl small
 pop {r4}
 pop {r3}
 mov lr,r3
 ldr r3,=0x08005B2B
 bx r3
fallback:
 pop {r0,r1,r2,r3}
 pop {r4}
 pop {r3}
 mov lr,r3
 ldr r3,=0x086DF001
 bx r3
small:
 ldr r3,=0x089D1401
 bx r3
.ltorg
