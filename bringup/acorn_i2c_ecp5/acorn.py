import argparse
from litex_boards.platforms import sqrl_acorn
from litex_boards.targets.sqrl_acorn import CRG as _CRG
from litex.build.generic_platform import *
from litex.soc.integration.common import get_mem_data
from litex.soc.integration.soc_core import SoCCore, soc_core_argdict, soc_core_args
from litex.soc.integration.builder import Builder, builder_argdict, builder_args
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.cores.led import LedChaser
from litex.soc.cores.cpu import VexRiscv


_i2c_io = [
    ("i2c", 0,
        Subsignal("sda", Pins("Y12")),
        Subsignal("scl", Pins("Y11")),
        IOStandard("LVCMOS18"),
    ),
]


class I2CTestSoC(SoCCore):
    def __init__(self, platform, cpu, **kwargs):
        sys_clk_freq = int(50e6)
        SoCCore.__init__(self, platform, cpu_type=cpu.name, clk_freq=sys_clk_freq, **kwargs)
        self.submodules.crg = _CRG(platform, sys_clk_freq)
        self.add_constant("ROM_BOOT_ADDRESS", self.mem_map['main_ram'])
        self.submodules.i2c = I2CMaster(platform.request("i2c"))
        self.submodules.led = LedChaser(platform.request('user_led'), sys_clk_freq)
        self.add_jtagbone()


def main():
    parser = argparse.ArgumentParser()
    builder_args(parser)
    soc_core_args(parser)
    parser.add_argument("--build_gateware", action='store_true')
    parser.add_argument("--load", action="store_true", help="Load bitstream (to SRAM)")
    args = parser.parse_args()
    soc_kwargs = soc_core_argdict(args)
    builder_kwargs = builder_argdict(args)

    cpu = VexRiscv
    soc_kwargs['integrated_sram_size'] = 16 * 1024
    soc_kwargs["integrated_main_ram_size"] = 16 * 1024

    output_dir = builder_kwargs['output_dir'] = 'build'
    fw_file = os.path.join(output_dir, "software", "firmware", "firmware.bin")
    try:
        soc_kwargs['integrated_main_ram_init'] = get_mem_data(fw_file, cpu.endianness)
    except OSError:
        pass

    platform = sqrl_acorn.Platform()
    platform.add_extension(_i2c_io)
    soc = I2CTestSoC(platform, cpu=cpu, **soc_kwargs)
    builder = Builder(soc, **builder_kwargs)
    builder.add_software_package('firmware', src_dir=os.path.join(os.getcwd(), 'firmware'))
    builder.build(run=args.build_gateware)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))


if __name__ == "__main__":
    main()
