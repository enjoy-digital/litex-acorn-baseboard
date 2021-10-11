
                                  __   _ __      _  __    ___
                                 / /  (_) /____ | |/_/___/ _ |_______  _______
                                / /__/ / __/ -_)>  </___/ __ / __/ _ \/ __/ _ \
                               /____/_/\__/\__/_/|_|__ /_/ |_\__/\___/_/ /_//_/
                                 / _ )___ ____ ___ / /  ___  ___ ________/ /
                                / _  / _ `(_-</ -_) _ \/ _ \/ _ `/ __/ _  /
                               /____/\_,_/___/\__/_.__/\___/\_,_/_/  \_,_/
                                       Copyright 2021 / Enjoy-Digital

[> Intro
--------

![](hardware/acorn-baseboard-proto.jpg)

The LiteX-Acorn-Baseboard is a baseboard developed around the SQRL's Acorn board (or Nite/LiteFury) expanding their possibilities with:
- A PCIe X1 connector.
- A SFP connector.
- A M2 SATA slot.
- An EPC5 FPGA (connected to the Acorn through a SerDes link) and providing:
- A JTAG/UART port.
- A 1Gbps Ethernet port (RGMII).
- A HDMI Out port.
- A SDCard slot.
- 4 PMODs.
- 2 Buttons.
- A LCD.
- 2 SATA connectors (connected to the ECP5's SerDeses).

The board is mainly intended to be used as a development board for LiteX: From regression testing to development of new features; but can also
be a nice and cheap FPGA development board for developers willing to play with PCIe, SFP, SATA, etc... or wanting to create an standalone and
open source Linux platforms.

[> Prerequisites
----------------
- Python3, Vivado.
- Either a Vivado-compatible JTAG cable (native or XVCD), or OpenOCD.

[> Installing LiteX
-------------------
```sh
$ wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
$ chmod +x litex_setup.py
$ sudo ./litex_setup.py init install
```
... or follow the installation instructions if the LiteX Wiki: https://github.com/enjoy-digital/litex/wiki/Installation

[> Designs
----------

TODO

[> Contact
-------------
E-mail: florent@enjoy-digital.fr