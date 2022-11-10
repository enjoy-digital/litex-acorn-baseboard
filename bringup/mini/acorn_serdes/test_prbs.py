#!/usr/bin/env python3

#
# This file is part of LiteICLink.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# LiteICLink PRBS/BER test utility.

import sys
import time
import argparse

from litex import RemoteClient

# Constants ----------------------------------------------------------------------------------------

prbs_modes = {
    "disabled": 0b00,
    "prbs7":    0b01,
    "prbs15":   0b10,
    "prbs31":   0b11,
}

prbs_pause = 0b100

near_end_pma_loopback = 0b10

# SerDes -------------------------------------------------------------------------------------------

class SerDes:
    def __init__(self, wb, n):
        self.n  = n
        print(f"Creating Serdes{n}")
        present = False
        for k, v in wb.regs.d.items():
            if f"serdes{n}_" in k:
                setattr(self, k.replace(f"serdes{n}_", ""), v)
                present = True
        if not present:
            raise ValueError(f"Serdes{n} not present in design")

    def measure_clocks(self):
        if hasattr(self, "clock_latch"):
            print(f"Measuring Serdes{self.n} frequencies...")
            duration = 2
            self.clock_latch.write(1)
            tx_start = self.clock_tx_cycles.read()
            rx_start = self.clock_rx_cycles.read()
            time.sleep(duration)
            self.clock_latch.write(1)
            tx_end = self.clock_tx_cycles.read()
            rx_end = self.clock_rx_cycles.read()
            tx_cycles = (tx_end - tx_start) if tx_end > tx_start else (2**32 - tx_start) + tx_end
            rx_cycles = (rx_end - rx_start) if rx_end > rx_start else (2**32 - rx_start) + rx_end
            print("TX freq: {:10.3f}MHz".format((tx_cycles)/(duration*1e6)))
            print("RX freq: {:10.3f}MHz".format((rx_cycles)/(duration*1e6)))

    def configure(self, mode, square_wave, loopback):
        print(f"Configuring Serdes{self.n}...")

        if hasattr(self, "clock_aligner_disable"):
            print("Disabling Clock Aligner")
            self.clock_aligner_disable.write(0)

        if square_wave:
            print(f"Setting Square-wave mode.")
            self.tx_produce_square_wave.write(1)

        print(f"Setting PRBS to {mode.upper()} mode.")
        self.tx_prbs_config.write(prbs_modes[mode])
        self.rx_prbs_config.write(prbs_modes[mode])

        if loopback:
            print(f"Enabling Loopback.")
            self.loopback.write(near_end_pma_loopback)

    def unconfigure(self):
        print(f"Unconfiguring Serdes{self.n}...")

        if hasattr(self, "clock_aligner_disable"):
            print("Enabling Clock Aligner.")
            self.clock_aligner_disable.write(0)

        print("Disabling Square-wave.")
        self.tx_produce_square_wave.write(0)

        print("Disabling PRBS.")
        self.tx_prbs_config.write(prbs_modes["disabled"])
        self.rx_prbs_config.write(prbs_modes["disabled"])

        print("Disabling Loopback.")
        self.loopback.write(0)

# PRBS Test ----------------------------------------------------------------------------------------

def prbs_test(csr_csv="csr.csv", port=1234, serdes=0, mode="prbs7", square_wave=False, loopback=False, duration=60):
    wb = RemoteClient(csr_csv=csr_csv, port=port)
    wb.open()

    # Create SerDes
    serdes = SerDes(wb, serdes)

    # Measure SerDes clocks
    serdes.measure_clocks()

    # Configure SerDes
    serdes.configure(mode, square_wave, loopback)

    # Run PRBS/BER Test
    print("Running PRBS/BER test...")
    first            = True
    errors           = 0
    errors_last      = 0
    errors_total     = 0
    duration_current = 0
    interval         = 0.5
    try:
        while duration_current < duration:
            # Interval / Duration
            time.sleep(interval)
            duration_current += interval
            # Errors
            serdes.rx_prbs_config.write(prbs_pause | prbs_modes[mode])
            errors = serdes.rx_prbs_errors.read()
            serdes.rx_prbs_config.write(prbs_modes[mode])
            if errors < errors_last:
                errors_last -= 1 << 32
            if not first:
                errors_total += (errors - errors_last)
            # Log
            print("Errors: {:10d} / Duration: {:5.2f}s / BER: {:1.3e} ".format(
                errors - errors_last,
                duration_current,
                errors_total/(duration_current*5e9)))
            first       = False
            errors_last = errors
    except KeyboardInterrupt:
        pass

    # Unconfigure Serdes
    serdes.unconfigure()

    wb.close()

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteICLink PRBS/BER test utility")
    parser.add_argument("--csr-csv",     default="csr.csv",   help="CSR configuration file")
    parser.add_argument("--port",        default="1234",      help="Host bind port")
    parser.add_argument("--serdes",      default="0",         help="Serdes")
    parser.add_argument("--mode",        default="prbs7",     help="PRBS mode: prbs7 (default), prbs15 or prbs31")
    parser.add_argument("--square-wave", action="store_true", help="Generate Square-wave on TX")
    parser.add_argument("--duration",    default="60",        help="Test duration (default=10)")
    parser.add_argument("--loopback",    action="store_true", help="Enable internal loopback")
    args = parser.parse_args()

    prbs_test(
        csr_csv     = args.csr_csv,
        port        = int(args.port, 0),
        serdes      = int(args.serdes, 0),
        mode        = args.mode,
        square_wave = args.square_wave,
        loopback    = args.loopback,
        duration    = int(args.duration, 0)
    )

if __name__ == "__main__":
    main()
