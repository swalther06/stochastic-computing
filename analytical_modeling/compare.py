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


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-M', type=int, default=None, help='Override all workload M dims')
    p.add_argument('-N', type=int, default=None, help='Override all workload N dims')
    p.add_argument('-K', type=int, default=None, help='Override all workload K dims')
    p.add_argument('--array-h',  type=int,   default=64,   dest='array_h')
    p.add_argument('--array-w',  type=int,   default=64,   dest='array_w')
    p.add_argument('--precision', type=int,  default=8)
    p.add_argument('--clock',     type=float, default=1e-9)
    p.add_argument('--synthesize', action='store_true',
                   help='Run DC synthesis to populate energy values before modeling')
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
        e = Energy(M, N, K, precision=args.precision, clock=args.clock)
        if args.synthesize:
            e.synthesize()

        ugemm = uGEMM_Arch(M, N, K, args.array_h, args.array_w,
                           acc_type="uNSADD", mul_type="uMUL-IS-unipolar",
                           clock=args.clock, precision=args.precision, energy=e)
        rows.append({
            'workload': name, 'arch': 'uGEMM',
            'cycles':   ugemm.get_cycles(),
            'energy_pJ': ugemm.get_energy() * 1e12,
        })

        binmodel = BinarySystolic_Arch(M, N, K, args.array_h, args.array_w,
                                       precision=args.precision, clock=args.clock, energy=e)
        rows.append({
            'workload': name, 'arch': 'Binary',
            'cycles':   binmodel.get_cycles(),
            'energy_pJ': binmodel.get_energy() * 1e12,
        })

        # usys = uSystolic_Arch(M, N, K, clock=args.clock, precision=args.precision, energy=e)
        # rows.append({'workload': name, 'arch': 'uSystolic',
        #              'cycles': usys.get_cycles(),
        #              'energy_pJ': usys.get_energy() * 1e12})

        # camb = CambriconU_Arch(M, N, K, clock=args.clock, precision=args.precision, energy=e)
        # rows.append({'workload': name, 'arch': 'CambriconU',
        #              'cycles': camb.get_cycles(),
        #              'energy_pJ': camb.get_energy() * 1e12})

    df = pd.DataFrame(rows)

    print("\nEnergy (pJ):")
    print(df.pivot(index='workload', columns='arch', values='energy_pJ'))
    print("\nCycles:")
    print(df.pivot(index='workload', columns='arch', values='cycles'))

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nWrote results to {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
