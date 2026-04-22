#!/usr/bin/env python3

#
# This file is part of LiteX-Acorn-Baseboard.
#
# Copyright (c) 2021-2026 Enjoy-Digital <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).
#
# SQRL Acorn cards ship with SPI-flash write protection enabled (a fallback from
# their mining-firmware past), so a freshly received board must first be
# unprotected before any new bitstream can be written.
#
# Examples:
#   ./flash.py --unprotect               # first-time unlock
#   ./flash.py --flash                   # flash the default LiteX bitstream
#   ./flash.py --unprotect --flash       # full first-time bring-up (both steps)
#   ./flash.py --flash --bitstream my.bin

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_CABLE        = "ft4232"
DEFAULT_FPGA_PART    = "xc7a200tfbg484"
DEFAULT_BITSTREAM_URL = "https://github.com/enjoy-digital/todo/files/15022745/litex_acorn_baseboard_mini.zip"
CACHE_DIR            = Path(__file__).resolve().parent / "prebuilt"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def require_openfpgaloader():
    if shutil.which("openFPGALoader") is None:
        sys.exit("error: openFPGALoader not found in PATH. See https://github.com/trabucayre/openFPGALoader")


def fetch_default_bitstream(url):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Reuse a cached .bin if we've already extracted one.
    cached = sorted(CACHE_DIR.glob("*.bin"))
    if cached:
        return cached[0]
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "bitstream.zip"
        print(f"Downloading default bitstream from {url} ...")
        try:
            urllib.request.urlretrieve(url, zip_path)
        except Exception as e:
            sys.exit(f"error: failed to download bitstream: {e}\n"
                     f"       pass --bitstream PATH to use a local .bin instead.")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(CACHE_DIR)
    bins = sorted(CACHE_DIR.glob("*.bin"))
    if not bins:
        sys.exit(f"error: no .bin file found after extracting {url}")
    return bins[0]


def unprotect(cable, fpga_part):
    print("==> Removing SPI-flash write protection")
    run(["openFPGALoader", "-c", cable, f"--fpga-part={fpga_part}", "--unprotect-flash"])


def flash_bitstream(cable, fpga_part, bitstream):
    print(f"==> Flashing {bitstream}")
    run(["openFPGALoader", "-c", cable, f"--fpga-part={fpga_part}", "-f", str(bitstream)])


def main():
    parser = argparse.ArgumentParser(
        description = "Production flash utility for LiteX-Acorn-Baseboard-Mini + SQRL Acorn CLE215(+).",
        formatter_class = argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--unprotect",     action="store_true", help="Remove SPI-flash write protection (needed once on fresh Acorns).")
    parser.add_argument("--flash",         action="store_true", help="Flash the bitstream to SPI flash.")
    parser.add_argument("--bitstream",     default=None,        help="Path to a local .bin bitstream (default: download the reference LiteX bitstream).")
    parser.add_argument("--bitstream-url", default=DEFAULT_BITSTREAM_URL, help="URL of the default bitstream archive (.zip).")
    parser.add_argument("--cable",         default=DEFAULT_CABLE,         help=f"openFPGALoader cable (default: {DEFAULT_CABLE}).")
    parser.add_argument("--fpga-part",     default=DEFAULT_FPGA_PART,     help=f"FPGA part (default: {DEFAULT_FPGA_PART}).")
    args = parser.parse_args()

    if not (args.unprotect or args.flash):
        parser.error("specify at least one of --unprotect / --flash (both may be combined; --unprotect runs first).")

    require_openfpgaloader()

    if args.unprotect:
        unprotect(args.cable, args.fpga_part)

    if args.flash:
        bitstream = Path(args.bitstream) if args.bitstream else fetch_default_bitstream(args.bitstream_url)
        if not bitstream.exists():
            sys.exit(f"error: bitstream not found: {bitstream}")
        flash_bitstream(args.cable, args.fpga_part, bitstream)


if __name__ == "__main__":
    main()
