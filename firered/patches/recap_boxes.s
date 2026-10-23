.syntax unified
.cpu arm7tdmi
.thumb
.text

/* Explicit, site-specific display entries. Never classify a caller by LR.
   Native getter/rename paths remain untouched. BL stays inside high ROM;
   the original aligned 8-byte site jumps here with LDR/BX, not Thumb2. */
.macro entry site, continuation, loadop=0, index=-1
.balign 4
.global box_\site
.thumb_func
box_\site:
 .if \loadop
 .hword \loadop
 .endif
 push {r4,lr}
 bl box_alias_existing
 pop {r4}
 pop {r3}
 mov lr,r3
 adds r1,r0,#0
 .if \index >= 0
 movs r0,#\index
 .endif
 ldr r3,=\continuation
 bx r3
 .ltorg
.endm

.equ box_alias_existing,0x08FFB3F0
entry 1153B4,0x081153BD,0,0
entry 1153CC,0x081153D5,0,2
entry 11543A,0x08115441,0x7920
entry 1154C6,0x081154CD,0x7920
entry 115544,0x0811554D,0,0
entry 11555C,0x08115565,0,2
entry 1155C0,0x081155C9,0,0
entry 11562C,0x08115635,0,0
entry 1156A2,0x081156A9,0x78A0
entry 115702,0x08115709,0x7820
entry 115726,0x0811572D,0x7860
