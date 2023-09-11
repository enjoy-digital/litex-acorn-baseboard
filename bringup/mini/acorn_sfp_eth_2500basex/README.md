[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.
- SFP 2500-Base-X <-> RJ45 module in SFP0.

[> Build
--------
./sqrl_acorn.py --build --load

[> Check
--------
ping 192.168.1.50 responding.
