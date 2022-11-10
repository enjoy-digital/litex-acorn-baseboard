[> Setup
--------
- Power from USB-C (J9).
- JTAG HS2 to Acorn.
- Board in PCIe slot (J1).

[> Build
--------
./sqrl_acorn.py --with-pcie --build --load

[> Check
--------
Board seen with lspci.
