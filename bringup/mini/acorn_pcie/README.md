[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.
- Board in PCIe slot.

[> Build
--------
./sqrl_acorn.py --with-pcie --build --load

Or, to keep the bitstream across power cycles, flash it to the SPI flash:

./sqrl_acorn.py --with-pcie --build --flash

[> Check
--------
Board seen with lspci (Xilinx vendor ID 10ee, device ID 7021 for X1):

lspci -d 10ee:

The first Acorn LED is a LED chaser (bitstream loaded), the second one reflects the PCIe link status.

Note: the host only enumerates PCIe devices at boot, so a bitstream loaded while the host is
running will not appear directly in lspci. The host has to re-enumerate the bus:
- With --load: do a warm reboot of the host. Since the baseboard is powered from its own USB-C
  (J9), the FPGA keeps its configuration across the reboot.
- With --flash: power-cycle the board (or the host) so the FPGA boots from the SPI flash, then
  boot the host.
- A PCIe rescan without reboot (sudo sh -c "echo 1 > /sys/bus/pci/rescan") may also work on some
  hosts, but is not reliable: a reboot is the recommended method.
