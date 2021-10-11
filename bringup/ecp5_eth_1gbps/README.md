[> Setup
--------
- Power from USB-C (J9).
- JTAG from USB-C (J7).

[> Build
--------
python3 -m litex_boards.targets.litex_m2_baseboard --with-etherbone --build --load

[> Check
--------
Verify that the board can be pinged at 192.168.1.50.
