[> Setup
--------
- Power from USB-C (J9).
- JTAG from USB-C (J7).

[> Build
--------
python3 -m litex_boards.targets.litex_acorn_baseboard --integrated-main-ram-size=0x2000 --with-lcd --build --load

[> Check
--------

litex_term /dev/ttyUSBX

    litex> i2c_scan
           0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
    0x00: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    0x10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    0x20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    0x30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
    0x40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    0x50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    0x60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    0x70: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --

cd firmware && make
litex_term /dev/ttyUSBX --kernel=firmware.bin
lcd
