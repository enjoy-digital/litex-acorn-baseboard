#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Build/Use:
# ./litex_acorn_baseboard.py --linerate=1.25e9 --build --load
# litex_server --uart --uart-port=/dev/ttyUSBX --bind-port=1235
# litex_cli --port=1235 --csr-csv=ecp5.csv --regs
# ./test_prbs.py --csr-csv=ecp5.csv --port=1235

import os
import argparse
import sys

from migen import *

from litex_boards.platforms import litex_acorn_baseboard

from litex.build.lattice.trellis import trellis_args, trellis_argdict
from litex.build.generic_platform import Pins, IOStandard
from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from litex.soc.cores.code_8b10b import K

from liteiclink.serdes.serdes_ecp5 import SerDesECP5PLL, SerDesECP5

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, refclk_from_pll, refclk_freq):
        self.rst = Signal()
        self.clock_domains.cd_por = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys = ClockDomain()

        # # #

        # Clk / Rst
        clk50 = platform.request("clk50")
        rst_n = platform.request("user_btn", 0)

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(clk50)
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~por_done | ~rst_n | self.rst)
        pll.register_clkin(clk50, 50e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        if refclk_from_pll:
            self.clock_domains.cd_ref = ClockDomain(reset_less=True)
            pll.create_clkout(self.cd_ref, refclk_freq)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCMini):
    def __init__(self, sys_clk_freq, linerate, connector="m2"):
        platform = litex_acorn_baseboard.Platform(toolchain="trellis")

        # SoCMini ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on LiteX M2 Baseboard")

        # UARTBone ---------------------------------------------------------------------------------
        self.add_uartbone()

        # CRG --------------------------------------------------------------------------------------
        refclk_from_pll = True
        refclk_freq     = 150e6
        self.submodules.crg = _CRG(platform, sys_clk_freq, refclk_from_pll, refclk_freq)

        # SerDes RefClk ----------------------------------------------------------------------------
        if refclk_from_pll:
            refclk = self.crg.cd_ref.clk
        else:
            refclk_pads = platform.request("refclk", 0)
            refclk = Signal()
            self.specials.extref0 = Instance("EXTREFB",
                i_REFCLKP     = refclk_pads.p,
                i_REFCLKN     = refclk_pads.n,
                o_REFCLKO     = refclk,
                p_REFCK_PWDNB = "0b1",
                p_REFCK_RTERM = "0b0",  # terminated with external resistor
                # p_REFCK_DCBIAS_EN = 1
            )
            # self.extref0.attr.add(("LOC", "EXTREF0"))

        # SerDes PLL -------------------------------------------------------------------------------
        serdes_pll = SerDesECP5PLL(refclk, refclk_freq=refclk_freq, linerate=linerate)
        self.submodules += serdes_pll
        print(serdes_pll)

        # SerDes -----------------------------------------------------------------------------------
        tx_pads = platform.request(connector + "_tx")
        rx_pads = platform.request(connector + "_rx")
        self.submodules.serdes0 = serdes0 = SerDesECP5(serdes_pll, tx_pads, rx_pads,
            dual        = 0,
            channel     = 0,
            rx_polarity = 0,
            tx_polarity = 0,
        )
        #self.comb += serdes0.init.rst.eq(self.crg.pll.reset)
        serdes0.add_stream_endpoints()
        serdes0.add_controls()
        serdes0.add_clock_cycles()
        platform.add_period_constraint(serdes0.txoutclk, 1e9/serdes0.tx_clk_freq)
        platform.add_period_constraint(serdes0.rxoutclk, 1e9/serdes0.rx_clk_freq)

        # Test -------------------------------------------------------------------------------------
        counter = Signal(32)
        self.sync.tx += counter.eq(counter + 1)

        # K28.5 and slow counter --> TX
        self.comb += [
            serdes0.sink.valid.eq(1),
            serdes0.sink.ctrl.eq(0b1),
            serdes0.sink.data[:8].eq(K(28, 5)),
            serdes0.sink.data[8:].eq(counter[26:]),
        ]

        platform.add_extension([
            ("user_led", 0, Pins("pmod1:0"), IOStandard("LVCMOS33")),
            ("user_led", 1, Pins("pmod1:1"), IOStandard("LVCMOS33")),
            ("user_led", 2, Pins("pmod1:2"), IOStandard("LVCMOS33")),
            ("user_led", 3, Pins("pmod1:3"), IOStandard("LVCMOS33")),
            ("user_led", 4, Pins("pmod1:4"), IOStandard("LVCMOS33")),
            ("user_led", 5, Pins("pmod1:5"), IOStandard("LVCMOS33")),
            ("user_led", 6, Pins("pmod1:6"), IOStandard("LVCMOS33")),
            ("user_led", 7, Pins("pmod1:7"), IOStandard("LVCMOS33")),
        ])

        # RX (slow counter) --> Leds
        self.comb += serdes0.source.ready.eq(1)

        rx_byte = Signal(8)
        self.sync.rx += [
            serdes0.rx_align.eq(1),
            # No word aligner, so look for K28.5 and redirect the other byte to the leds
            If(serdes0.source.data[0:8] == K(28, 5),
                rx_byte.eq(serdes0.source.data[8:]),
            ).Else(
                rx_byte.eq(serdes0.source.data[0:]),
            ),
            platform.request("user_led", 3).eq(~rx_byte[0]),
        ]

        # Analyzer ---------------------------------------------------------------------------------
        from litescope import LiteScopeAnalyzer
        self.submodules.analyzer = LiteScopeAnalyzer([
            serdes0.init.fsm,
            serdes0.init.tx_lol,
            serdes0.init.rx_lol,
            serdes0.init.rx_los,
            ], depth=512)

        # Leds -------------------------------------------------------------------------------------
        sys_counter = Signal(32)
        self.sync.sys += sys_counter.eq(sys_counter + 1)
        self.comb += platform.request("user_led", 0).eq(sys_counter[26])

        rx_counter = Signal(32)
        self.sync.rx += rx_counter.eq(rx_counter + 1)
        self.comb += platform.request("user_led", 1).eq(rx_counter[26])

        tx_counter = Signal(32)
        self.sync.tx += tx_counter.eq(tx_counter + 1)
        self.comb += platform.request("user_led", 2).eq(tx_counter[26])

        self.comb += platform.request("user_led", 4).eq(serdes0.init.tx_lol)
        self.comb += platform.request("user_led", 5).eq(serdes0.init.rx_lol)
        self.comb += platform.request("user_led", 6).eq(serdes0.init.rx_los)


# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on LiteX Acorn Baseboard")
    parser.add_argument("--build",        action="store_true", help="Build bitstream.")
    parser.add_argument("--load",         action="store_true", help="Load bitstream.")
    parser.add_argument("--flash",        action="store_true", help="Flash bitstream to SPI Flash.")
    parser.add_argument("--sys-clk-freq", default=50e6,        help="System clock frequency.")
    parser.add_argument("--linerate",     default="3.0e9",     help="Linerate (default: 3.0e9)")
    args = parser.parse_args()

    soc = BaseSoC(
        sys_clk_freq = int(float(args.sys_clk_freq)),
        linerate     = float(args.linerate)
    )
    builder = Builder(soc, csr_csv="ecp5.csv")
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

    if args.flash:
        prog = soc.platform.create_programmer()
        prog.flash(None, os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
