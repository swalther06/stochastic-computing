"""compare.py — top-level driver

Usage examples:
    uv run python compare.py
    uv run python compare.py --synthesize
    uv run python compare.py --synthesize -M 128 -N 128 -K 64
    uv run python compare.py -M 64 -N 64 -K 64 --array-h 32 --array-w 32 --precision 4
"""
import argparse
import os
import pandas as pd

from energy import Energy
from uSystolic_AM import uSystolic_Arch
from uGEMM_AM     import uGEMM_Arch
from CambriconU_AM import CambriconU_Arch
from binary_AM import BinarySystolic_Arch

OUTPUT_CSV = 'outputs/comparison.csv'

WORKLOADS = [
    ('64x64x64',     64,   64,   64),
    ('128x128x128', 128,  128,  128),
    ('256x256x256', 256,  256,  256),
    ('512x512x512', 512,  512,  512),
]

IFMAP_SRAM_KB = 64
FILTER_SRAM_KB = 64
OFMAP_SRAM_KB = 64


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-M', type=int, default=None, help='Override all workload M dims')
    p.add_argument('-N', type=int, default=None, help='Override all workload N dims')
    p.add_argument('-K', type=int, default=None, help='Override all workload K dims')
    p.add_argument('--array-h',  type=int,   default=64,   dest='array_h')
    p.add_argument('--array-w',  type=int,   default=64,   dest='array_w')
    p.add_argument('--precision', type=int,  default=8)
    p.add_argument('--frequency', type=float, default=1e9,
                   help='Clock frequency in Hz (default: 1e9 = 1 GHz)')
    p.add_argument('--synthesize', action='store_true',
                   help='Run DC synthesis to populate compute-component energy values')
    p.add_argument('--cacti', action='store_true',
                   help='Run CACTI to populate SRAM read/write/leakage energy values')
    return p.parse_args()


def main():
    args = parse_args()

    workloads = WORKLOADS
    if args.M is not None or args.N is not None or args.K is not None:
        M = args.M or WORKLOADS[0][1]
        N = args.N or WORKLOADS[0][2]
        K = args.K or WORKLOADS[0][3]
        workloads = [(f'{M}x{N}x{K}', M, N, K)]

    rows = []
    for name, M, N, K in workloads:
        e = Energy(M, N, K,
                   array_h=args.array_h, array_w=args.array_w,
                   precision=args.precision, freq=args.frequency,
                   ifmap_sram_kB=IFMAP_SRAM_KB,
                   filter_sram_kB=FILTER_SRAM_KB,
                   ofmap_sram_kB=OFMAP_SRAM_KB)
        if args.synthesize:
            e.synthesize()
        if args.cacti:
            e.run_cacti()
        if not args.synthesize and not args.cacti:
            print(f'[{name}] Using cached energy values (pass --synthesize and/or --cacti to refresh)')

        ugemm = uGEMM_Arch(M, N, K, args.array_h, args.array_w,
                           acc_type="uNSADD", mul_type="uMUL-IS-unipolar",
                           freq=args.frequency, precision=args.precision, energy=e,
                           include_memory=False, ifmap_sram_kB=IFMAP_SRAM_KB, 
                           filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)
        rows.append({
            'workload': name, 'arch': 'uGEMM',
            'cycles':   ugemm.get_cycles(),
            'energy_pJ': ugemm.get_energy() * 1e12,
        })

        binmodel = BinarySystolic_Arch(M, N, K, args.array_h, args.array_w,
                                       precision=args.precision, freq=args.frequency, energy=e,
                                       include_memory=False, ifmap_sram_kB=IFMAP_SRAM_KB, 
                                       filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)
        rows.append({
            'workload': name, 'arch': 'Binary',
            'cycles':   binmodel.get_cycles(),
            'energy_pJ': binmodel.get_energy() * 1e12,
        })

        usys = uSystolic_Arch(M, N, K, args.array_h, args.array_w,
                              freq=args.frequency, precision=args.precision,
                              energy=e, include_memory=False, ifmap_sram_kB=IFMAP_SRAM_KB, 
                              filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)
        rows.append({
            'workload': name, 'arch': 'uSystolic',
            'cycles':   usys.get_cycles(),
            'energy_pJ': usys.get_energy() * 1e12,
        })

        # camb = CambriconU_Arch(M, N, K, freq=args.frequency, precision=args.precision, energy=e)
        # rows.append({'workload': name, 'arch': 'CambriconU',
        #              'cycles': camb.get_cycles(),
        #              'energy_pJ': camb.get_energy() * 1e12})

    df = pd.DataFrame(rows)
    workload_order = [w[0] for w in workloads]

    print("\nEnergy (pJ):")
    print(df.pivot(index='workload', columns='arch', values='energy_pJ').reindex(workload_order))
    print("\nCycles:")
    print(df.pivot(index='workload', columns='arch', values='cycles').reindex(workload_order))

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nWrote results to {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
