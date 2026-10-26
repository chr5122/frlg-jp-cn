.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.balign 4

/* Dedicated read entries: no inference from LR or caller address. */
.global forgotten_get
.thumb_func
forgotten_get:
    movs r2,#0xe0
    b get_common
.global teach_get
.thumb_func
teach_get:
    movs r2,#0xe8
get_common:
    push {r2,lr}
    ldr r3,=0x0811d8b1
    bl call_r3
    pop {r2}
    lsls r2,r2,#1
    adds r0,r0,r2
    pop {r1}
    bx r1

/* Replays 11CDD0..11CDD7; resumes at the original following BL.
 * Incoming r0=object+0x77, r1=move*16, r2=CN table.
 * Copy to object+0x1C0; original subsequent r0=object retained.
 */
.global forgotten_write
.thumb_func
forgotten_write:
    push {r2,lr}
    adds r1,r1,r2
    adds r0,#0xff
    adds r0,#0x4a
    ldr r3,=0x08008901
    bl call_r3
    pop {r2,r3}
    mov lr,r3
    movs r0,r4
    ldr r3,=0x0811cdd9
    bx r3

/* Replays 11CF00..11CF07; resumes at the original epilogue.
 * Incoming r0=object+0x7F, r1=move*16. Copy to object+0x1D0.
 */
.global teach_write
.thumb_func
teach_write:
    push {r2,lr}
    ldr r2,=0x0871f444
    adds r1,r1,r2
    adds r0,#0xff
    adds r0,#0x52
    ldr r3,=0x08008901
    bl call_r3
    pop {r2,r3}
    mov lr,r3
    ldr r3,=0x0811cf09
    bx r3

.thumb_func
call_r3:
    bx r3
.balign 4
.ltorg
