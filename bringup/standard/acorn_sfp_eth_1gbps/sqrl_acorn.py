#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex_boards.platforms import sqrl_acorn

from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from litex.soc.cores.clock import *
from litex.soc.cores.led import LedChaser

from litex.build.generic_platform import Subsignal, Pins
from liteeth.phy.a7_gtp import QPLLSettings, QPLL
from liteeth.phy.a7_1000basex import A7_1000BASEX


# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_idelay = ClockDomain()

        # Clk/Rst
        clk200 = platform.request("clk200")

        # PLL
        self.submodules.pll = pll = S7PLL()
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(clk200, 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_idelay, 200e6)
        # Ignore sys_clk to pll.clkin path created by SoC's rst.
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# BaseSoC -----------------------------------------------------------------------------------------

class BaseSoC(SoCMini):
    def __init__(self, variant="cle-215+", sys_clk_freq=int(125e6), with_led_chaser=True, **kwargs):
        platform = sqrl_acorn.Platform(variant=variant)

        # SoCCore ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Acorn CLE-101/215(+)")

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform, sys_clk_freq)

        # Etherbone --------------------------------------------------------------------------------

        _eth_io = [
            ("sfp", 0,
                Subsignal("txp", Pins("D7")),
                Subsignal("txn", Pins("C7")),
                Subsignal("rxp", Pins("D9")),
                Subsignal("rxn", Pins("C9")),
            ),
        ]
        platform.add_extension(_eth_io)

        # phy
        qpll_settings = QPLLSettings(
            refclksel  = 0b001,
            fbdiv      = 4,
            fbdiv_45   = 5,
            refclk_div = 1
        )
        qpll = QPLL(ClockSignal("sys"), qpll_settings)
        self.submodules += qpll
        self.submodules.ethphy = A7_1000BASEX(
            qpll_channel = qpll.channels[0],
            data_pads    = self.platform.request("sfp"),
            sys_clk_freq = self.clk_freq,
            rx_polarity  = 1,  # inverted on acorn
            tx_polarity  = 0   # inverted on acorn and on base board
        )
        platform.add_platform_command("set_property SEVERITY {{Warning}} [get_drc_checks REQP-49]")
        self.add_etherbone(phy=self.ethphy)

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.submodules.leds = LedChaser(
                pads         = platform.request_all("user_led"),
                sys_clk_freq = sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Acorn CLE-101/215(+)")
    parser.add_argument("--build",           action="store_true", help="Build bitstream")
    parser.add_argument("--load",            action="store_true", help="Load bitstream")
    parser.add_argument("--flash",           action="store_true", help="Flash bitstream")
    parser.add_argument("--variant",         default="cle-215+",  help="Board variant: cle-215+, cle-215 or cle-101")
    parser.add_argument("--sys-clk-freq",    default=125e6,       help="System clock frequency")
    builder_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(
        variant      = args.variant,
        sys_clk_freq = int(float(args.sys_clk_freq)),
    )

    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

    if args.flash:
        prog = soc.platform.create_programmer()
        prog.flash(0, os.path.join(builder.gateware_dir, soc.build_name + ".bin"))


if __name__ == "__main__":
    main()
