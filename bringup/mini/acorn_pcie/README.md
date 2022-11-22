[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.
- Board in PCIe slot.

[> Build
--------
./sqrl_acorn.py --with-pcie --build --load

[> Check
--------
Board seen with lspci.
