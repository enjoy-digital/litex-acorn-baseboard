[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.

[> Build
--------
./sqrl_acorn.py --uart-name=jtag_uart --build --load
litex_server --jtag --jtag-config=openocd_xc7_ft232.cfg

[> Check
--------
LiteX BIOS showing up in litex_term.
