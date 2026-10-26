.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global synthetic_copy
.thumb_func
@ Independent synthetic byte-FF copier for isolated CPU tests, NOT game code.
synthetic_copy:
    movs r2, r0
copy_byte:
    ldrb r3, [r1]
    strb r3, [r2]
    adds r1, #1
    adds r2, #1
    cmp r3, #255
    bne copy_byte
    subs r0, r2, #1
    bx lr
