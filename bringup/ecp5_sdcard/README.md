[> Setup
--------
- Power from USB-C (J9).
- JTAG from USB-C (J7).
- SDCard.

[> Build
--------
python3 -m litex_boards.targets.litex_acorn_baseboard --integrated-main-ram-size=0x1000 --with-sdcard --build --load

[> Check
--------

litex_term /dev/ttyUSBX

Without SDCard in slot:

    litex> sdcard_init
    Initialize SDCard... Failed.

With SDCard in slot:

    litex> sdcard_init
    Initialize SDCard... Successful.

