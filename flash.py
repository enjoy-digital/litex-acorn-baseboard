#!/usr/bin/env python3

#
# This file is part of LiteX-Acorn-Baseboard.
#
# Copyright (c) 2021-2026 Enjoy-Digital <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).
#
# SQRL Acorn cards ship with their SPI flash block-protected and, on some
# units, with the Configuration Register bits set for QPI / 4-byte addressing.
# The Acorn's SPI flash is a 32 MiB S25FL256S, but bitstreams for this FPGA
# fit in the first 16 MiB, so we stay in 3-byte addressing land.
#
# Both --unprotect and --flash drive OpenOCD + a BSCAN-SPI proxy. OpenOCD's
# BSCAN-USER path works even when the FPGA's full startup sequence stalls on
# a Done=0 (which openFPGALoader's SOJ stub does on some boards), so this
# is the robust path that works everywhere we've seen.
#
# Examples:
#   ./flash.py --unprotect               # one-time: clear SR/CR protection
#   ./flash.py --flash                   # program default bitstream
#   ./flash.py --unprotect --flash       # full first-time bring-up
#   ./flash.py --flash --bitstream my.bin

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

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

    Sends software-reset + WRSR with SR=0x00, CR=0x00 directly through the
    Xilinx USER1 register — openocd 0.11's jtagspi driver has no raw-SPI
    command and no `protect` op, so we scan the bytes ourselves. No erase, no
    program. Run this once on a fresh Acorn so subsequent --flash calls work.
    """
    require("openocd")
    try:
        from litex.build.openocd import OpenOCD, get_openocd_cmd
    except ImportError:
        sys.exit("error: --unprotect needs the 'litex' Python package (for the OpenOCD helper).\n"
                 "       install it per https://github.com/enjoy-digital/litex/wiki/Installation")
    print("==> Resetting SPI flash + clearing SR/CR/PPB via OpenOCD (BSCAN-SPI proxy)")
    prog   = OpenOCD(OPENOCD_CONFIG, FLASH_PROXY)
    config = prog.find_config()
    proxy  = prog.find_flash_proxy()
    # USER1 on Xilinx 7-series = IR 0x02 — selects the BSCAN-SPI proxy's SPI DR.
    # Each drscan is one SPI transaction (CS asserts on SHIFT-DR, deasserts on UPDATE-DR).
    # Bytes on the wire are MSB-first; openocd drscan shifts LSB-first, so each byte
    # is pre bit-reversed. openocd prints TDO capture as hex; for an RDSR drscan 16
    # bits with value 0xa0 the response SR comes back bit-reversed in the upper byte
    # of the printed value (the lower byte covers cmd-send, flash not driving MISO).
    resen      = _rev8(0x66)                                                              # Software Reset Enable
    reset      = _rev8(0x99)                                                              # Software Reset
    wren       = _rev8(0x06)                                                              # Write Enable
    wrsr_all   = _rev8(0x01) | (_rev8(0x00) << 8) | (_rev8(0x00) << 16)                   # 24-bit: WRSR cmd + SR=0x00 + CR=0x00
    ppb_erase  = _rev8(0xE4)                                                              # Erase all non-volatile per-sector PPB lock bits
    rdsr       = _rev8(0x05)                                                              # Read Status Register
    rdcr       = _rev8(0x35)                                                              # Read Configuration Register
    script = "; ".join([
        "init",
        f"jtagspi_init 0 {{{proxy}}}",
        # Diagnostic: read SR/CR before we touch anything.
        'echo "--- pre-unprotect: RDSR, RDCR (response in upper byte of drscan hex, bit-reversed) ---"',
        "irscan xc7.tap 0x02", f"drscan xc7.tap 16 0x{rdsr:02x}",
        "irscan xc7.tap 0x02", f"drscan xc7.tap 16 0x{rdcr:02x}",
        # Software reset — back to power-on defaults (clears QPI/4-byte/pending ops).
        'echo "--- software reset (RESEN 0x66, RESET 0x99) ---"',
        "irscan xc7.tap 0x02", f"drscan xc7.tap 8 0x{resen:02x}",
        "irscan xc7.tap 0x02", f"drscan xc7.tap 8 0x{reset:02x}",
        "sleep 50",
        # WREN + WRSR SR=0, CR=0 — clears SRWD + BP[2:0] + QUAD + LC.
        'echo "--- WREN + WRSR SR=0 CR=0 ---"',
        "irscan xc7.tap 0x02", f"drscan xc7.tap 8 0x{wren:02x}",
        "irscan xc7.tap 0x02", f"drscan xc7.tap 24 0x{wrsr_all:06x}",
        "sleep 200",
        # WREN + PPB_ERASE — clears per-sector persistent protection bits set by
        # factory firmware (PPB_LOCK defaults to 1 after power-up so this is legal).
        'echo "--- WREN + PPB_ERASE (0xE4) ---"',
        "irscan xc7.tap 0x02", f"drscan xc7.tap 8 0x{wren:02x}",
        "irscan xc7.tap 0x02", f"drscan xc7.tap 8 0x{ppb_erase:02x}",
        "sleep 300",
        # Diagnostic: read SR/CR after. If protection cleared, both should be 0x00.
        'echo "--- post-unprotect: RDSR, RDCR ---"',
        "irscan xc7.tap 0x02", f"drscan xc7.tap 16 0x{rdsr:02x}",
        "irscan xc7.tap 0x02", f"drscan xc7.tap 16 0x{rdcr:02x}",
        "exit",
    ])
    prog.call([get_openocd_cmd(), "-f", config, "-c", script])


def flash_via_openocd(bitstream):
    """Program *bitstream* to SPI flash via OpenOCD + BSCAN-SPI proxy."""
    require("openocd")
    try:
        from litex.build.openocd import OpenOCD
    except ImportError:
        sys.exit("error: --flash needs the 'litex' Python package (for the OpenOCD helper).\n"
                 "       install it per https://github.com/enjoy-digital/litex/wiki/Installation")
    print(f"==> Flash {bitstream} via OpenOCD (BSCAN-SPI proxy)")
    prog = OpenOCD(OPENOCD_CONFIG, FLASH_PROXY)
    prog.flash(0, str(bitstream))


def main():
    parser = argparse.ArgumentParser(
        description = "Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).",
    )
    parser.add_argument("--unprotect", action="store_true",       help="Clear SPI-flash block-protect + CR via OpenOCD (needed once on fresh Acorns).")
    parser.add_argument("--flash",     action="store_true",       help="Flash the bitstream via OpenOCD.")
    parser.add_argument("--bitstream", default=DEFAULT_BITSTREAM, help=f"Path to the .bin bitstream (default: {DEFAULT_BITSTREAM.relative_to(Path(__file__).resolve().parent)}).")
    args = parser.parse_args()

    if not (args.unprotect or args.flash):
        parser.error("specify at least one of --unprotect / --flash.")

    if args.unprotect:
        unprotect_via_openocd()

    if args.flash:
        bitstream = Path(args.bitstream)
        if not bitstream.exists():
            sys.exit(f"error: bitstream not found: {bitstream}")
        flash_via_openocd(bitstream)


if __name__ == "__main__":
    main()
