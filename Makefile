PYTHON ?= python3
ARM_PREFIX ?= arm-none-eabi-

.PHONY: test check asm
test:
	PYTHONPATH=shared $(PYTHON) -B -m unittest discover -s tests -v
check:
	$(PYTHON) -B tools/check.py
asm:
	mkdir -p build
	$(ARM_PREFIX)as -mcpu=arm7tdmi -mthumb firered/patches/recap_boxes.s -o build/fr_boxes.o
	$(ARM_PREFIX)ld -Ttext=0x08EDA810 -e box_1153B4 build/fr_boxes.o -o build/fr_boxes.elf
	$(ARM_PREFIX)objcopy -O binary build/fr_boxes.elf build/fr_boxes.bin
	$(ARM_PREFIX)as -mcpu=arm7tdmi -mthumb leafgreen/patches/recap_boxes.s -o build/lg_boxes.o
	$(ARM_PREFIX)ld -Ttext=0x08FFC110 -e box_11538C build/lg_boxes.o -o build/lg_boxes.elf
	$(ARM_PREFIX)objcopy -O binary build/lg_boxes.elf build/lg_boxes.bin
	$(ARM_PREFIX)as -mcpu=arm7tdmi -mthumb shared/patches/cn_glyph.s -o build/cn_glyph.o
	$(ARM_PREFIX)ld -Ttext=0x08F00000 -e cn_decode_glyph build/cn_glyph.o -o build/cn_glyph.elf
	$(ARM_PREFIX)objcopy -O binary build/cn_glyph.elf build/cn_glyph.bin
