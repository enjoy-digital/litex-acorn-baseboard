[> Setup
--------
- Power from USB-C (J9).
- JTAG from USB-C (J7).
- HDMI monitor connected to HDMI Out (J14).

[> Build
--------
python3 -m litex_boards.targets.litex_acorn_baseboard --with-video-terminal --build --load

[> Check
--------
Verify that LiteX BIOS prompt is displayed on the HDMI monitor.
