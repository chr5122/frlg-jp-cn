.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global summary_controls
.thumb_func
@ Local summary-controls bridge; entered with native caller stack and r6 text.
@ Bind SMALL_MEASURE and SUMMARY_CONTINUATION independently for each game.
summary_controls:
    push {r0,r4,r5,lr}
    movs r0, r6
    bl SMALL_MEASURE
    movs r4, r0
    ldr r0, [sp]
    movs r1, #12
    muls r0, r1
    ldr r1, =0x02020430
    adds r0, r0, r1
    ldrb r1, [r0,#1]
    lsls r1, r1, #3
    ldrb r0, [r0,#3]
    lsls r0, r0, #3
    adds r0, r0, r1
    cmp r0, #236
    bls edge_ready
    movs r0, #236
edge_ready:
    subs r0, r0, r1
    movs r2, #8
    cmp r0, r4
    blo restored
    subs r2, r0, r4
restored:
    ldr r1, [sp,#12]
    mov lr, r1
    pop {r0,r4,r5}
    add sp, #4
    movs r1, #0
    str r1, [sp,#4]
    str r6, [sp,#8]
    ldr r3, =SUMMARY_CONTINUATION
    bx r3
.ltorg
