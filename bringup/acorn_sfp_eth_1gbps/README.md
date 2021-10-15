[> Setup
--------
- Power from USB-C (J9).
- JTAG HS2 to Acorn.
- SFP 1000-BaseX Module (J3).

[> Build
--------
./sqrl_acorn.py --cpu-type=None --integrated-main-ram-size=0x100 --build --load

[> Check
--------
Verify that the board can be pinged at 192.168.1.50.
