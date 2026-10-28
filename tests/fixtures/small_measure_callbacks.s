@ Synthetic metrics callbacks, not the original game's glyph/icon functions.
.syntax unified
.cpu arm7tdmi
.thumb
.text
.global icon_stub, native_stub
.thumb_func
icon_stub:
    adds r0,#8
    bx lr
.org 0x20
.thumb_func
native_stub:
    adds r0,#4
    ldr r1,=0x03003E60
    strb r0,[r1]
    bx lr
.ltorg
