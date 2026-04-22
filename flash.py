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


def _rev8(b):
    """Bit-reverse an 8-bit value (openocd's drscan shifts LSB-first, SPI is MSB-first)."""
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


def unprotect_via_openocd():
    """Clear block-protect bits in the SPI flash via OpenOCD + BSCAN-SPI proxy.

    Sends WREN (0x06) then WRSR 0x00 (clears SRWD + BP[2:0]) directly through
    the Xilinx USER1 register — openocd 0.11's jtagspi driver has no raw-SPI
    command and no `protect` op, so we scan the bytes ourselves. No erase, no
    program; once the block-protect bits are cleared openFPGALoader's SOJ path
    takes over for the actual erase + program.
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
    # USER1 on Xilinx 7-series = IR 0x02 — selects the BSCAN-SPI proxy's SPI DR.
    # Each drscan is one SPI transaction (CS asserts on SHIFT-DR, deasserts on UPDATE-DR).
    wren      = _rev8(0x06)
    wrsr_cmd  = (_rev8(0x00) << 8) | _rev8(0x01)  # 16-bit DR: cmd 0x01, data 0x00
    script = "; ".join([
        "init",
        f"jtagspi_init 0 {{{proxy}}}",
        # WREN
        "irscan xc7.tap 0x02",
        f"drscan xc7.tap 8 0x{wren:02x}",
        # WRSR 0x00 — clears SRWD + BP[2:0]
        "irscan xc7.tap 0x02",
        f"drscan xc7.tap 16 0x{wrsr_cmd:04x}",
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
