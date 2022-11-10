BUILD_DIR?=../..

include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = isr.o main.o i2c_spi.o crt0.o
CFLAGS += -Wall -Wextra -Werror

all: firmware.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@

firmware.elf: $(OBJECTS)
	$(CC) $(LDFLAGS) \
		-T $(FIRMWARE_DIRECTORY)/linker.ld \
		-N -o $@ \
		$(OBJECTS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		$(LIBS:lib%=-l%)
	chmod -x $@


crt0.o: $(CPU_DIRECTORY)/crt0.S
	$(assemble)

%.o: $(FIRMWARE_DIRECTORY)/%.cpp
	$(compilexx)

%.o: $(FIRMWARE_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) firmware.elf firmware.bin .*~ *~

.PHONY: all clean load
