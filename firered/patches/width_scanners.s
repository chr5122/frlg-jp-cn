.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global width_fixed
.global width_variable
@ Frozen production operand ABI, NOT an original-ROM installer.
@ Pointer classification intentionally retains the existing broad RAM ranges.
width_fixed:
 movs r0,r4
 bl cn_address
 cmp r0,#0
 beq fixed_native
 movs r0,r2
 ldrb r0,[r4,r0]
 cmp r0,#CN_FONT_MAX_PAGE
 bhi fixed_native
 adds r2,#2
 adds r5,#1
 lsls r5,r5,#24
 lsrs r5,r5,#24
 ldr r0,=0x08005D59
 bx r0
fixed_native:
 ldr r0,=0x08005D4D
 bx r0
width_variable:
 movs r0,r4
 bl cn_address
 cmp r0,#0
 beq variable_native
 ldrb r0,[r4,#1]
 cmp r0,#CN_FONT_MAX_PAGE
 bhi variable_native
 bl WIDTH_ALIAS
 adds r4,#2
 ldr r0,=0x08005F6D
 bx r0
variable_native:
 ldr r0,=0x08005E83
 bx r0
cn_address:
 ldr r1,=0x086D0000
 cmp r0,r1
 blo check_ram
 ldr r1,=0x08730000
 cmp r0,r1
 blo is_cn
 b not_cn
check_ram:
 lsrs r1,r0,#24
 cmp r1,#2
 beq ewram
 cmp r1,#3
 bne not_cn
 ldr r1,=0x03008000
 cmp r0,r1
 blo is_cn
 b not_cn
ewram:
 ldr r1,=0x02040000
 cmp r0,r1
 bhs not_cn
is_cn:
 movs r0,#1
 bx lr
not_cn:
 movs r0,#0
 bx lr
