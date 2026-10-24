#!/usr/bin/env python3

#
# This file is part of LiteX-Acorn-Baseboard.
#
# SPDX-License-Identifier: BSD-2-Clause

# Verilator simulation of the HTTP server, connected to the host through a tap0 interface (root
# required):
# ./sim.py
# curl http://192.168.1.50

import os
import argparse

from migen import *
from migen.genlib.io import CRG

from litex.gen import *

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from liteeth.phy.model import LiteEthPHYModel
from liteeth.core import LiteEthIPCore

from http_server import LiteEthTCPHTTPServer, http_response

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("sys_clk", 0, Pins(1)),
    ("sys_rst", 0, Pins(1)),
    ("eth_clocks", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(SimPlatform):
    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

# SimSoC -------------------------------------------------------------------------------------------

class SimSoC(SoCMini):
    def __init__(self, ip_address="192.168.1.50", mac_address=0x10e2d5000000, index="index.html"):
        platform     = Platform()
        sys_clk_freq = int(1e6)

        # SoCMini ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, sys_clk_freq, ident="LiteX HTTP Server Simulation")

        # CRG --------------------------------------------------------------------------------------
        self.crg = CRG(platform.request("sys_clk"))

        # Ethernet PHY -----------------------------------------------------------------------------
        self.ethphy = LiteEthPHYModel(platform.request("eth"))

        # Ethernet Core (MAC + ARP + IP + ICMP) ----------------------------------------------------
        self.ethcore = LiteEthIPCore(
            phy               = self.ethphy,
            mac_address       = mac_address,
            ip_address        = ip_address,
            clk_freq          = sys_clk_freq,
            with_sys_datapath = True,
        )

        # HTTP Server ------------------------------------------------------------------------------
        with open(index, "rb") as f:
            response = http_response(f.read())
        self.http_server = LiteEthTCPHTTPServer(
            ip         = self.ethcore.ip,
            ip_address = ip_address,
            response   = response,
        )

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX HTTP Server Simulation.")
    parser.add_argument("--ip-address",     default="192.168.1.50",  help="HTTP Server IP address.")
    parser.add_argument("--remote-ip",      default="192.168.1.100", help="Host (tap0) IP address.")
    parser.add_argument("--index",          default="index.html",    help="HTML page to serve.")
    parser.add_argument("--trace",          action="store_true",     help="Enable VCD tracing.")
    parser.add_argument("--non-interactive", action="store_true",    help="Run without interactive console.")
    args = parser.parse_args()

    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": args.remote_ip})

    soc = SimSoC(ip_address=args.ip_address, index=args.index)
    builder = Builder(soc, output_dir=os.path.join("build", "sim"), compile_software=False)
    builder.build(sim_config=sim_config, trace=args.trace, interactive=not args.non_interactive)

if __name__ == "__main__":
    main()
