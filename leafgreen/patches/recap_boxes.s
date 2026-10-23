.syntax unified
.cpu arm7tdmi
.thumb
.text
/* Site-specific display redirects. No LR caller classification, no BLX.
   LeafGreen's existing display alias is too far for Thumb1 BL, so use an
   explicit local BX-r3 trampoline, never a guessed FireRed address. */
.macro entry site, continuation, loadop=0, index=-1
.balign 4
.global box_\site
.thumb_func
box_\site:
 .if \loadop
 .hword \loadop
 .endif
 push {r4,lr}
 ldr r3,=0x08745A51
 bl call_r3
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
entry 11538C,0x08115395,0,0
entry 1153A4,0x081153AD,0,2
entry 115412,0x08115419,0x7920
entry 11549E,0x081154A5,0x7920
entry 11551C,0x08115525,0,0
entry 115534,0x0811553D,0,2
entry 115598,0x081155A1,0,0
entry 115604,0x0811560D,0,0
entry 11567A,0x08115681,0x78A0
entry 1156DA,0x081156E1,0x7820
entry 1156FE,0x08115705,0x7860
.thumb_func
call_r3:
 bx r3
.balign 4
