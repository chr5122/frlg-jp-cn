.syntax unified
.cpu arm7tdmi
.thumb
.section .text
ldr r1,=0x08B64A40
subs r1,r4,r1
cmp r1,#0xA0
bhi ordinary
beq spacer
movs r0,#10
b done
spacer:
movs r0,#2
b done
ordinary:
movs r0,#12
done:
ldr r1,=0x03003E60
bx lr
.ltorg
