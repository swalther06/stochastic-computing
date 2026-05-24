import os
from scalesim.scale_sim import scalesim
import pandas as pd

def _write_config(array_h = 64, array_w = 64):
    cfg = f"""[general]
run_name = binary_64x64

[architecture_presets]
ArrayHeight:    {array_h}
ArrayWidth:     {array_w}
IfmapSramSzkB:  1024
FilterSramSzkB: 1024
OfmapSramSzkB:  1024
IfmapOffset:    0
FilterOffset:   10000000
OfmapOffset:    20000000
Bandwidth:      10
Dataflow:       ws
MemoryBanks:    1
ReadRequestBuffer:  32
WriteRequestBuffer: 32

[layout]
IfmapCustomLayout:      False
IfmapSRAMBankBandwidth: 10
IfmapSRAMBankNum:       10
IfmapSRAMBankPort:      2
FilterCustomLayout:     False
FilterSRAMBankBandwidth: 10
FilterSRAMBankNum:      10
FilterSRAMBankPort:     2

[sparsity]
SparsitySupport: false
SparseRep:       ellpack_block
OptimizedMapping: false
BlockSize:        8
RandomNumberGeneratorSeed: 40

[run_presets]
InterfaceBandwidth: CALC
UseRamulatorTrace:  False
"""
    os.makedirs('configs', exist_ok=True)
    with open('configs/binary_64x64.cfg', 'w') as f:
        f.write(cfg)


def _write_topology(workloads):
    os.makedirs('topologies', exist_ok=True)
    with open('topologies/compare_shapes.csv', 'w') as f:
        f.write("Layer, M, N, K,\n")
        for name, M, N, K in workloads:
            f.write(f"{name}, {M}, {N}, {K},\n")


def _write_stub_layout():
    """Stub layout file — required by scale-sim-v2 even when custom layouts off."""
    os.makedirs('layouts', exist_ok=True)
    header = ("Layer name, IFMAP Height Intraline Factor, IFMAP Width Intraline Factor, "
              "Filter Height Intraline Factor, Filter Width Intraline Factor, "
              "Channel Intraline Factor, Num Filter Intraline Factor, "
              "IFMAP Height Intraline Order, IFMAP Width Intraline Order, "
              "Channel Intraline Order, IFMAP Height Interline Order, "
              "IFMAP Width Interline Order, Channel Interline Order, "
              "Num Filter Intraline Order, Channel Intraline Order, "
              "Filter Height Intraline Order, Filter Width Intraline Order, "
              "Num Filter Interline Order, Channel Interline Order, "
              "Filter Height Interline Order, Filter Width Interline Order,\n")
    with open('layouts/stub_layout.csv', 'w') as f:
        f.write(header)


# ===== binary baseline via SCALE-Sim =====
def binary_via_scalesim(workloads):
    """Run SCALE-Sim once for all workloads. Returns dict of report DataFrames."""
    _write_config()
    _write_topology(workloads)
    _write_stub_layout()
    sim = scalesim(
        save_disk_space=True, verbose=False,
        config='configs/binary_64x64.cfg',
        topology='topologies/compare_shapes.csv',
        layout='layouts/stub_layout.csv',
        input_type_gemm=True,
    )
    sim.run_scale(top_path='outputs/compare/')

    run_dir = 'outputs/compare/binary_64x64'

    def _load(fname):
        df = pd.read_csv(f'{run_dir}/{fname}')
        df.columns = df.columns.str.strip()
        return df

    return {
        'compute':   _load('COMPUTE_REPORT.csv'),
        'bandwidth': _load('BANDWIDTH_REPORT.csv'),
        'access':    _load('DETAILED_ACCESS_REPORT.csv'),
    }

