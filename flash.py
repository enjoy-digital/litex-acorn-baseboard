#!/usr/bin/env python3

#
# This file is part of LiteX-Acorn-Baseboard.
#
# Copyright (c) 2021-2026 Enjoy-Digital <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).
#
# SQRL Acorn cards ship with their SPI flash in a state that openFPGALoader's
# spi-over-jtag proxy can't reach directly ("Read ID failed"). The proven
# workaround is to first flash a bitstream through OpenOCD + a BSCAN-SPI proxy;
# once that first write goes through, the card is unlocked and subsequent
# writes can use the faster openFPGALoader path.
#
# Examples:
#   ./flash.py --unprotect                 # one-time unlock (openocd + default bitstream)
#   ./flash.py --flash                     # fast re-flash via openFPGALoader
#   ./flash.py --flash --bitstream my.bin  # fast re-flash of a custom bitstream
#   ./flash.py --unprotect --bitstream my.bin  # unlock while flashing a custom bitstream

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_CABLE     = "ft4232"
DEFAULT_FPGA_PART = "xc7a200tfbg484"
DEFAULT_BITSTREAM = Path(__file__).resolve().parent / "prebuilt" / "litex_acorn_baseboard_mini.bin"

# OpenOCD assets used for the unlock path. LiteX's OpenOCD helper auto-downloads
# both files on first use from its config/flash-proxy repositories.
OPENOCD_CONFIG = "openocd_xc7_ft4232.cfg"
FLASH_PROXY    = "bscan_spi_xc7a200t.bit"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def require(tool, hint=""):
    if shutil.which(tool) is None:
        sys.exit(f"error: {tool} not found in PATH." + (f" {hint}" if hint else ""))


def unprotect_via_openocd(bitstream):
    """Flash *bitstream* through OpenOCD + BSCAN-SPI proxy.

    This also unlocks the factory-protected flash on fresh Acorn cards — the
    first successful write through this path clears whatever state was
    blocking openFPGALoader's SOJ from reading the flash ID.
    """
    require("openocd")
    try:
        from litex.build.openocd import OpenOCD
    except ImportError:
        sys.exit("error: --unprotect needs the 'litex' Python package (for the OpenOCD helper).\n"
                 "       install it per https://github.com/enjoy-digital/litex/wiki/Installation")
    print(f"==> Unlock + flash {bitstream} via OpenOCD (BSCAN-SPI proxy)")
    prog = OpenOCD(OPENOCD_CONFIG, FLASH_PROXY)
    prog.flash(0, str(bitstream))


def flash_via_openfpgaloader(cable, fpga_part, bitstream):
    require("openFPGALoader", "See https://github.com/trabucayre/openFPGALoader")
    print(f"==> Flash {bitstream} via openFPGALoader")
    run(["openFPGALoader", "-c", cable, f"--fpga-part={fpga_part}", "-f", str(bitstream)])


def main():
    parser = argparse.ArgumentParser(
        description = "Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).",
    )
    parser.add_argument("--unprotect", action="store_true",       help="First-time unlock: flash via OpenOCD + BSCAN-SPI proxy (handles factory-locked flash).")
    parser.add_argument("--flash",     action="store_true",       help="Fast re-flash via openFPGALoader (use after the card has been unlocked).")
    parser.add_argument("--bitstream", default=DEFAULT_BITSTREAM, help=f"Path to the .bin bitstream (default: {DEFAULT_BITSTREAM.relative_to(Path(__file__).resolve().parent)}).")
    parser.add_argument("--cable",     default=DEFAULT_CABLE,     help=f"openFPGALoader cable (default: {DEFAULT_CABLE}).")
    parser.add_argument("--fpga-part", default=DEFAULT_FPGA_PART, help=f"FPGA part (default: {DEFAULT_FPGA_PART}).")
    args = parser.parse_args()

    if not (args.unprotect or args.flash):
        parser.error("specify at least one of --unprotect / --flash.")

    bitstream = Path(args.bitstream)
    if not bitstream.exists():
        sys.exit(f"error: bitstream not found: {bitstream}")

    if args.unprotect:
        unprotect_via_openocd(bitstream)

    if args.flash:
        flash_via_openfpgaloader(args.cable, args.fpga_part, bitstream)


if __name__ == "__main__":
    main()
