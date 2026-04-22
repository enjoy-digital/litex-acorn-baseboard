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
import os
import re
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


def _find_openocd():
    """Locate an openocd binary that supports `jtagspi cmd` (added in 0.12).

    Stock Ubuntu 22.04 ships 0.11 which lacks the command; this function
    probes a few common alternative install locations. Returns (binary,
    scripts_dir) where scripts_dir may be None to fall back to defaults.
    """
    # Highest priority: user-provided OPENOCD env var — assume they know.
    env = os.environ.get("OPENOCD")
    if env:
        return env, None

    home = str(Path.home())
    candidates = [
        # System openocd (sufficient on Ubuntu 24.04+).
        ("openocd",                                                  None),
        # LiteX-built openocd (from contrib build scripts).
        (f"{home}/dev/litex/tmp/openocd/src/openocd",                f"{home}/dev/litex/tmp/openocd/tcl"),
        # oss-cad-suite bundled openocd.
        ("/opt/oss-cad-suite/bin/openocd",                           "/opt/oss-cad-suite/share/openocd/scripts"),
    ]
    for binary, scripts in candidates:
        path = shutil.which(binary) if not binary.startswith("/") else (binary if Path(binary).is_file() else None)
        if not path:
            continue
        try:
            out = subprocess.run([path, "--version"], capture_output=True, text=True).stderr
            m = re.search(r"Open On-Chip Debugger\s+(\d+)\.(\d+)", out)
            if m and (int(m.group(1)), int(m.group(2))) >= (0, 12):
                return path, scripts
        except Exception:
            continue
    return None, None


def unprotect_via_openocd():
    """Clear block-protect bits in the SPI flash via OpenOCD + BSCAN-SPI proxy.

    Sends software-reset + WRSR with SR=0x00, CR=0x00 directly through the
    Xilinx USER1 register — openocd 0.11's jtagspi driver has no raw-SPI
    command and no `protect` op, so we scan the bytes ourselves. No erase, no
    program. Run this once on a fresh Acorn so subsequent --flash calls work.
    """
    require("openocd")
    try:
        from litex.build.openocd import OpenOCD
    except ImportError:
        sys.exit("error: --unprotect needs the 'litex' Python package (for the OpenOCD helper).\n"
                 "       install it per https://github.com/enjoy-digital/litex/wiki/Installation")
    binary, scripts = _find_openocd()
    if binary is None:
        sys.exit(
            "error: --unprotect needs openocd 0.12+ (for the 'jtagspi cmd' subcommand).\n"
            "       Ubuntu 22.04 ships 0.11, which does not have it. Options:\n"
            "         - upgrade to openocd 0.12+\n"
            "         - install oss-cad-suite (https://github.com/YosysHQ/oss-cad-suite-build)\n"
            "         - build openocd from source and point OPENOCD=/path/to/openocd at it\n"
        )
    print(f"==> Resetting SPI flash + clearing SR/CR/PPB via OpenOCD (BSCAN-SPI proxy) [{binary}]")
    prog   = OpenOCD(OPENOCD_CONFIG, FLASH_PROXY)
    config = prog.find_config()
    proxy  = prog.find_flash_proxy()
    # Uses openocd's `jtagspi cmd <bank> <num_read> <cmd_byte> [data...]` — exposed
    # natively by the jtagspi driver (openocd >= 0.12). Our earlier raw irscan+drscan
    # attempts produced 0xffff captures on the Acorn: the jtagspi driver's internal
    # USER1+DR scan works, but two separate Tcl irscan/drscan calls do not reach the
    # BSCAN-SPI proxy the same way on these cards. Using `jtagspi cmd` routes through
    # the same single-queue path that jtagspi_init uses for flash probe.
    script = "; ".join([
        "init",
        f"jtagspi_init 0 {{{proxy}}}",
        'echo "--- pre-unprotect ---"',
        'echo "  RDSR pre : [jtagspi cmd 0 1 0x05]"',
        'echo "  RDCR pre : [jtagspi cmd 0 1 0x35]"',
        'echo "--- software reset (RESEN 0x66, RESET 0x99) ---"',
        "jtagspi cmd 0 0 0x66",
        "jtagspi cmd 0 0 0x99",
        "sleep 50",
        'echo "--- WREN + WRSR SR=0 CR=0 ---"',
        "jtagspi cmd 0 0 0x06",
        "jtagspi cmd 0 0 0x01 0x00 0x00",
        "sleep 200",
        'echo "--- WREN + PPB_ERASE (0xE4) ---"',
        "jtagspi cmd 0 0 0x06",
        "jtagspi cmd 0 0 0xe4",
        "sleep 300",
        'echo "--- post-unprotect ---"',
        'echo "  RDSR post: [jtagspi cmd 0 1 0x05]"',
        'echo "  RDCR post: [jtagspi cmd 0 1 0x35]"',
        "exit",
    ])
    cmd = [binary]
    if scripts:
        cmd += ["-s", scripts]
    cmd += ["-f", config, "-c", script]
    prog.call(cmd)


def flash_via_openfpgaloader(bitstream):
    """Program *bitstream* to SPI flash via openFPGALoader (fast path; requires
    the flash to be unprotected first — run --unprotect if the card is fresh)."""
    require("openFPGALoader", "See https://github.com/trabucayre/openFPGALoader")
    print(f"==> Flash {bitstream} via openFPGALoader")
    run(["openFPGALoader", "-c", "ft4232", "--fpga-part=xc7a200tfbg484", "-f", str(bitstream)])


def main():
    parser = argparse.ArgumentParser(
        description = "Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).",
    )
    parser.add_argument("--unprotect", action="store_true",       help="Clear SPI-flash block-protect + CR via OpenOCD (needed once on fresh Acorns).")
    parser.add_argument("--flash",     action="store_true",       help="Flash the bitstream via openFPGALoader (after unlock).")
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
        flash_via_openfpgaloader(bitstream)


if __name__ == "__main__":
    main()
