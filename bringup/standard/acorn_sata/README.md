[> Setup
--------
- Power from USB-C (J9).
- JTAG from USB-C (J7).
- JTAG HS2 to Acorn.
- SATA M2 SSD (J8).

[> Build
--------
python3 acorn.py --gen=1 --with-analyzer --build --load
python3 -m litex_boards.targets.litex_acorn_baseboard --cpu-type=None --build --load

[> Check
--------
./test_init.py

    Success (retries: 0)

./test_bist.py -i

    Serial Number: PNY21242106160100189
    Firmware Revision: CS900BB3
    Model Number: PNY CS900 M.2 250GB SSD
    Capacity: 232.89 GiB
    SATA Gen1: 1
    SATA Gen2: 1
    SATA Gen3: 1
    48 bits LBA supported: 1
