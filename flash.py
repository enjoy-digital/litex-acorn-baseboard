#!/usr/bin/env python3

#
# This file is part of LiteX-Acorn-Baseboard.
#
# Copyright (c) 2021-2026 Enjoy-Digital <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).
#
# SQRL Acorn cards ship with their SPI flash block-protected — openFPGALoader's
# own spi-over-jtag proxy can't even read the flash JEDEC ID in that state, so
# --unprotect-flash has no chance. OpenOCD + a BSCAN-SPI proxy on the other
# hand can reach the flash fine (Read ID works), but its jtagspi driver doesn't
# support 4-byte addressing, which the 32 MiB S25FL256S on the Acorn needs for
# a full program.
#
# The split here mirrors what actually works: OpenOCD does the minimum — clear
# the block-protect bits in the status register — then openFPGALoader takes
# over for the actual erase + program (which it handles correctly, including
# 4-byte addressing).
#
# Examples:
#   ./flash.py --unprotect               # one-time: clear block-protect via openocd
#   ./flash.py --flash                   # program default bitstream via openFPGALoader
#   ./flash.py --unprotect --flash       # full first-time bring-up
#   ./flash.py --flash --bitstream my.bin

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


def unprotect_via_openocd():
    """Clear block-protect bits in the SPI flash via OpenOCD + BSCAN-SPI proxy.

    Only issues WREN + WRSR 0x00 — no erase, no program. Once the block-protect
    bits are cleared the flash answers JEDEC ID reads and openFPGALoader's SOJ
    path can take over for the actual erase + program.
    """
    require("openocd")
    try:
        from litex.build.openocd import OpenOCD, get_openocd_cmd
    except ImportError:
        sys.exit("error: --unprotect needs the 'litex' Python package (for the OpenOCD helper).\n"
                 "       install it per https://github.com/enjoy-digital/litex/wiki/Installation")
    print("==> Clearing block-protect bits in SPI flash via OpenOCD (BSCAN-SPI proxy)")
    prog   = OpenOCD(OPENOCD_CONFIG, FLASH_PROXY)
    config = prog.find_config()
    proxy  = prog.find_flash_proxy()
    script = "; ".join([
        "init",
        f"jtagspi_init 0 {{{proxy}}}",
        "jtagspi cmd 0 0 0x06",           # WREN  (Write Enable)
        "jtagspi cmd 0 0 0x01 0x00",      # WRSR 0x00 (clear SRWD + BP[2:0])
        "sleep 200",
        "exit",
    ])
    prog.call([get_openocd_cmd(), "-f", config, "-c", script])


def flash_via_openfpgaloader(cable, fpga_part, bitstream):
    require("openFPGALoader", "See https://github.com/trabucayre/openFPGALoader")
    print(f"==> Flash {bitstream} via openFPGALoader")
    run(["openFPGALoader", "-c", cable, f"--fpga-part={fpga_part}", "-f", str(bitstream)])


def main():
    parser = argparse.ArgumentParser(
        description = "Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).",
    )
    parser.add_argument("--unprotect", action="store_true",       help="Clear SPI-flash block-protect via OpenOCD (needed once on fresh Acorns).")
    parser.add_argument("--flash",     action="store_true",       help="Flash the bitstream via openFPGALoader.")
    parser.add_argument("--bitstream", default=DEFAULT_BITSTREAM, help=f"Path to the .bin bitstream (default: {DEFAULT_BITSTREAM.relative_to(Path(__file__).resolve().parent)}).")
    parser.add_argument("--cable",     default=DEFAULT_CABLE,     help=f"openFPGALoader cable (default: {DEFAULT_CABLE}).")
    parser.add_argument("--fpga-part", default=DEFAULT_FPGA_PART, help=f"FPGA part (default: {DEFAULT_FPGA_PART}).")
    args = parser.parse_args()

    if not (args.unprotect or args.flash):
        parser.error("specify at least one of --unprotect / --flash.")

    if args.unprotect:
        unprotect_via_openocd()

    if args.flash:
        bitstream = Path(args.bitstream)
        if not bitstream.exists():
            sys.exit(f"error: bitstream not found: {bitstream}")
        flash_via_openfpgaloader(args.cable, args.fpga_part, bitstream)


if __name__ == "__main__":
    main()
