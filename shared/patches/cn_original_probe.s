.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global cn_probe_prefix
.type cn_probe_prefix, %function
.thumb_func

@ Exact-original Oak first-line PROBE ONLY, not a general CN engine.
@ Hook replaces eight bytes at RenderText's dispatch; r3=byte, r6=printer.
@ Intercept only font4 and an exact complete RAM copy of our immutable line.
@ All other streams, including native F7, retain native dispatch semantics.
cn_probe_prefix:
    cmp r3, #0xf7
    bne native_dispatch
    ldrb r0, [r6, #5]           @ template+4 is windowId, +5 is fontId
    cmp r0, #4
    bne native_dispatch
    push {r1-r5, r7, lr}
    sub sp, #4
    ldr r4, [r6]
    ldr r0, =PROBE_BUFFER + 4   @ first glyph's high-ID byte after FC06/font4
    cmp r4, r0
    blo rejected
    ldr r0, =PROBE_BUFFER + PROBE_LENGTH - 2
    cmp r4, r0
    bhs rejected               @ both ID bytes must precede the final FF
    ldr r1, =PROBE_BUFFER
    ldr r5, =PROBE_TEXT
    movs r7, #PROBE_LENGTH
compare_line:
    ldrb r0, [r1]
    ldrb r2, [r5]
    cmp r0, r2
    bne rejected
    adds r1, #1
    adds r5, #1
    subs r7, #1
    bne compare_line
    ldrb r0, [r4]
    ldrb r2, [r4, #1]
    lsls r0, r0, #8
    orrs r0, r2
    adds r4, #2
    str r4, [r6]
    ldr r1, =PROBE_CONFIG
    bl cn_decode_glyph
    add sp, #4
    pop {r1-r5, r7}
    pop {r0}
    mov lr, r0
    ldr r0, =PROBE_COPY_GLYPH
    bx r0
rejected:
    add sp, #4
    pop {r1-r5, r7}
    pop {r0}
    mov lr, r0
native_dispatch:
    adds r0, r3, #0
    subs r0, #0xf8
    cmp r0, #7
    bls native_switch
    @ Native glyph path immediately overwrites r0, preserving other inputs.
    ldr r0, =PROBE_NATIVE_GLYPH
    bx r0
native_switch:
    @ Original switch shifts r0, then overwrites r1 before reading it.
    ldr r1, =PROBE_NATIVE_SWITCH
    bx r1
.size cn_probe_prefix, .-cn_probe_prefix
