.syntax unified
.cpu arm7tdmi
.thumb
.section .text
ldrb r0,[r4,#1]
lsls r0,r0,#8
ldrb r1,[r4,#2]
orrs r0,r1
ldr r1,=0x092A
subs r0,r0,r1
cmp r0,#5
bhi ordinary
beq spacer
movs r0,#10
b done
spacer:
movs r0,#0
b done
ordinary:
movs r0,#12
done:
add r8,r0
bx lr
.ltorg
