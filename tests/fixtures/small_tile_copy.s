@ Synthetic test callback. Copies one 16-byte source tile verbatim into the
@ first half of a 32-byte scratch tile; not a native game decompressor.
.syntax unified
.cpu arm7tdmi
.thumb
.text
.global copy_test_tile
.thumb_func
copy_test_tile:
    movs r2, #0
1:  ldrb r3, [r0, r2]
    strb r3, [r1, r2]
    adds r2, #1
    cmp r2, #16
    bne 1b
    bx lr
