[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.
- PCIe loopback board.
- SFP loopback module.

[> Build
--------
./sqrl_acorn.py --connector=pcie --build --load

[> Check
--------
litex_server --uart --uart-port=/dev/ttyUSBX (X=1 if only the baseboard connected).
./test_prbs.py:
Creating Serdes0
Measuring Serdes0 frequencies...
TX freq:    126.362MHz
RX freq:    126.362MHz
Configuring Serdes0...
Setting PRBS to PRBS7 mode.
Running PRBS/BER test...
Errors:          2 / Duration:  0.50s / BER: 0.000e+00
Errors:          0 / Duration:  1.00s / BER: 0.000e+00
Errors:          0 / Duration:  1.50s / BER: 0.000e+00
Errors:          0 / Duration:  2.00s / BER: 0.000e+00
Errors:          0 / Duration:  2.50s / BER: 0.000e+00
Errors:          0 / Duration:  3.00s / BER: 0.000e+00
Errors:          0 / Duration:  3.50s / BER: 0.000e+00
Errors:          0 / Duration:  4.00s / BER: 0.000e+00
Errors:          0 / Duration:  4.50s / BER: 0.000e+00
