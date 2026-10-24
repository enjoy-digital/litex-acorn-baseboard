#!/usr/bin/env python3

#
# This file is part of LiteX-Acorn-Baseboard.
#
# SPDX-License-Identifier: BSD-2-Clause

# Build/Use ----------------------------------------------------------------------------------------
# Build/Load bitstream:
# ./sqrl_acorn.py --build --load
# ping 192.168.1.50
# curl http://192.168.1.50 (or open it in a web browser)

from migen import *

from litex.gen import *

import sqrl_acorn_platform as sqrl_acorn

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from litex.soc.cores.clock import *
from litex.soc.cores.led import LedChaser

from litex.build.generic_platform import Subsignal, Pins
from liteeth.phy.a7_gtp import QPLLSettings, QPLL
from liteeth.phy.a7_1000basex import A7_1000BASEX
from liteeth.core import LiteEthIPCore

from http_server import LiteEthTCPHTTPServer, http_response

# IOs ----------------------------------------------------------------------------------------------

_sfp_io = [
    ("sfp", 0,
        Subsignal("txp", Pins("D5")),
        Subsignal("txn", Pins("C5")),
        Subsignal("rxp", Pins("D11")),
        Subsignal("rxn", Pins("C11")),
    ),
    ("sfp", 1,
        Subsignal("txp", Pins("B4")),
        Subsignal("txn", Pins("A4")),
        Subsignal("rxp", Pins("B8")),
        Subsignal("rxn", Pins("A8")),
    ),
]

# CRG ----------------------------------------------------------------------------------------------

class CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst    = Signal()
        self.cd_sys = ClockDomain()

        # Clk/Rst
        clk200 = platform.request("clk200")

        # PLL
        self.pll = pll = S7PLL()
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(clk200, 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq, margin=0)
        # Ignore sys_clk to pll.clkin path created by SoC's rst.
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)

# BaseSoC -----------------------------------------------------------------------------------------

class BaseSoC(SoCMini):
    def __init__(self, variant="cle-215+", sys_clk_freq=156.25e6, sfp=0,
        mac_address     = 0x10e2d5000000,
        ip_address      = "192.168.1.50",
        index           = "index.html",
        with_led_chaser = True):
        platform = sqrl_acorn.Platform(variant=variant)
        platform.add_extension(_sfp_io)
        assert sys_clk_freq == 156.25e6

        # SoCMini ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, sys_clk_freq, ident="LiteX HTTP Server on Acorn CLE-101/215(+)")

        # CRG --------------------------------------------------------------------------------------
        self.crg = CRG(platform, sys_clk_freq)

        # Ethernet PHY (1000BASE-X over SFP) -------------------------------------------------------
        qpll_settings = QPLLSettings(
            refclksel  = 0b001,
            fbdiv      = 4,
            fbdiv_45   = 4,
            refclk_div = 1
        )
        self.qpll = qpll = QPLL(ClockSignal("sys"), qpll_settings)

        self.ethphy = A7_1000BASEX(
            qpll_channel = qpll.channels[0],
            data_pads    = platform.request("sfp", sfp),
            sys_clk_freq = sys_clk_freq,
            rx_polarity  = 1,  # Inverted on Acorn
            tx_polarity  = 0   # Inverted on Acorn and on baseboard.
        )
        platform.add_platform_command("set_property SEVERITY {{Warning}} [get_drc_checks REQP-49]")
        platform.add_period_constraint(self.ethphy.cd_eth_rx.clk, 1e9/self.ethphy.rx_clk_freq)
        platform.add_period_constraint(self.ethphy.cd_eth_tx.clk, 1e9/self.ethphy.tx_clk_freq)
        platform.add_false_path_constraints(self.crg.cd_sys.clk, self.ethphy.cd_eth_rx.clk, self.ethphy.cd_eth_tx.clk)

        # Ethernet Core (MAC + ARP + IP + ICMP) ----------------------------------------------------
        self.ethcore = ClockDomainsRenamer({
            "eth_tx": self.ethphy.cd_eth_tx.name,
            "eth_rx": self.ethphy.cd_eth_rx.name,
        })(LiteEthIPCore(
            phy               = self.ethphy,
            mac_address       = mac_address,
            ip_address        = ip_address,
            clk_freq          = sys_clk_freq,
            with_sys_datapath = True,
        ))

        # HTTP Server ------------------------------------------------------------------------------
        with open(index, "rb") as f:
            response = http_response(f.read())
        self.http_server = LiteEthTCPHTTPServer(
            ip         = self.ethcore.ip,
            ip_address = ip_address,
            response   = response,
        )

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.leds = LedChaser(
                pads         = platform.request_all("user_led"),
                sys_clk_freq = sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=sqrl_acorn.Platform, description="LiteX HTTP Server on Acorn CLE-101/215(+).")
    parser.add_target_argument("--flash",       action="store_true",         help="Flash bitstream.")
    parser.add_target_argument("--variant",     default="cle-215+",          help="Board variant (cle-215+, cle-215 or cle-101).")
    parser.add_target_argument("--sfp",         default=0, type=int,         choices=[0, 1], help="SFP port.")
    parser.add_target_argument("--ip-address",  default="192.168.1.50",     help="HTTP Server IP address.")
    parser.add_target_argument("--mac-address", default="0x10e2d5000000",    help="HTTP Server MAC address.")
    parser.add_target_argument("--index",       default="index.html",        help="HTML page to serve.")
    args = parser.parse_args()

    soc = BaseSoC(
        variant     = args.variant,
        sfp         = args.sfp,
        mac_address = int(args.mac_address, 0),
        ip_address  = args.ip_address,
        index       = args.index,
    )

    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

    if args.flash:
        prog = soc.platform.create_programmer()
        prog.flash(0, builder.get_bitstream_filename(mode="flash"))

if __name__ == "__main__":
    main()
