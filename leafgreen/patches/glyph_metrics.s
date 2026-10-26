.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global glyph_metrics
.thumb_func
glyph_metrics:
    ldr r1, =0x08B64AE0
    cmp r4, r1
    bne range_check
    movs r0, #2
    b done
range_check:
    ldr r1, =0x08B64A40
    cmp r4, r1
    blo ordinary
    ldr r1, =0x08B64AE0
    cmp r4, r1
    bhs ordinary
    movs r0, #10
    b done
ordinary:
    movs r0, #12
done:
    ldr r1, =0x03003E60
    bx lr
.ltorg
