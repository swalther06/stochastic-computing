"""compare_energy.py — top-level driver"""
import os
from math import ceil
import pandas as pd

import energy as energy
from uSystolic_AM import uSystolic_Arch
from uGEMM_AM     import uGEMM_Arch
from CambriconU_AM import CambriconU_Arch
from scalesim.scale_sim import scalesim


def _write_config():
    cfg = f"""[general]
run_name = binary_64x64

[architecture_presets]
ArrayHeight:    {ARRAY_H}
ArrayWidth:     {ARRAY_W}
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


# ===== knobs =====
ARRAY_H, ARRAY_W = 64, 64
PRECISION        = 8
CLOCK            = 1e-9

"""
WORKLOADS = [
    ('64x64x64',     64,   64,   64),
    ('128x128x128', 128,  128,  128),
    ('256x256x256', 256,  256,  256),
    ('512x512x512', 512,  512,  512),
]
"""


# ===== mapping functions for each architecture =====
# For now, workload size must be a multiple of array size
def usys_tiled(M, N, K):
    """uSystolic: M→rows, N→cols, K→temporal."""
    num_tiles = ceil(M / ARRAY_H) * ceil(N / ARRAY_W)
    tile = uSystolic_Arch(m=ARRAY_H, n=ARRAY_W, k=K,
                          clock=CLOCK, precision=PRECISION)
    return {
        'cycles': num_tiles * tile.get_cycles(),
        'energy': num_tiles * tile.get_energy(),
    }

def ugemm_tiled(M, N, K):
    """uGEMM: M→rows, N→cols, K→temporal."""
    num_tiles = ceil(M / ARRAY_H) * ceil(N / ARRAY_W)
    tile = uGEMM_Arch(m=ARRAY_H, n=ARRAY_W, k=K, acc_type="uNSADD", mul_type="uMUL-IS-unipolar",
                      clock=CLOCK, precision=PRECISION)
    return {
        'cycles': num_tiles * tile.get_cycles(),
        'energy': num_tiles * tile.get_energy(),
    }

def cambriconu_tiled(M, N, K):
    """CambriconU: M→rows, N→cols, K→temporal."""
    num_tiles = ceil(M / ARRAY_H) * ceil(N / ARRAY_W)
    tile = CambriconU_Arch(m=ARRAY_H, n=ARRAY_W, k=K,
                           clock=CLOCK, precision=PRECISION)
    return {
        'cycles': num_tiles * tile.get_cycles(),
        'energy': num_tiles * tile.get_energy(),
    }


# ===== binary baseline via SCALE-Sim =====
def binary_via_scalesim(workloads):
    """Run SCALE-Sim once for all workloads.

    Returns a dict of DataFrames keyed by report name:
        'compute'  -> COMPUTE_REPORT.csv   (cycles, stalls, utilization)
        'bandwidth'-> BANDWIDTH_REPORT.csv (per-operand SRAM/DRAM bandwidth)
        'access'   -> DETAILED_ACCESS_REPORT.csv (access counts + access cycles)
    """
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


def binary_energy(M, N, K):
    macs = M * N * K
    return macs * energy.__MAC_BINARY_INT8_ENERGY


# ===== assembly =====
def main():
    ss = binary_via_scalesim(WORKLOADS)

    rows = []
    for (name, M, N, K), ss_row in zip(WORKLOADS, ss.iterrows()):
        _, ss_data = ss_row   # ss.iterrows() yields (index, Series)

        # Run all three unary models
        r_usys  = usys_tiled(M, N, K)
        r_ugemm = ugemm_tiled(M, N, K)
        r_camb  = cambriconu_tiled(M, N, K)

        # Binary baseline
        binary_cyc = int(ss_data['Total Cycles'])
        binary_e   = binary_energy(M, N, K)

        rows += [
            {'workload': name, 'arch': 'uSystolic',
             'cycles': r_usys['cycles'],  'energy_pJ': r_usys['energy']  * 1e12},
            {'workload': name, 'arch': 'uGEMM',
             'cycles': r_ugemm['cycles'], 'energy_pJ': r_ugemm['energy'] * 1e12},
            {'workload': name, 'arch': 'CambriconU',
             'cycles': r_camb['cycles'],  'energy_pJ': r_camb['energy']  * 1e12},
            {'workload': name, 'arch': 'Binary',
             'cycles': binary_cyc,        'energy_pJ': binary_e * 1e12},
        ]

    df = pd.DataFrame(rows)

    print("\nEnergy (pJ):")
    print(df.pivot(index='workload', columns='arch', values='energy_pJ'))
    print("\nCycles:")
    print(df.pivot(index='workload', columns='arch', values='cycles'))


if __name__ == '__main__':
    main()