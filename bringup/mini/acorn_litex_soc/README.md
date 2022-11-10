[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.

[> Build
--------
./sqrl_acorn.py --build --load
litex_term /dev/ttyUSBX (X=1 if only the baseboard connected).

[> Check
--------
LiteX BIOS showing up in litex_term.
