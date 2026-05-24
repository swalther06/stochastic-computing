"""compare_energy.py — top-level driver"""
import os
from math import ceil
import pandas as pd

from uSystolic_AM import uSystolic_Arch
from uGEMM_AM     import uGEMM_Arch
from CambriconU_AM import CambriconU_Arch
from binary_AM import BinarySystolic_Arch


# ===== knobs =====
ARRAY_H, ARRAY_W = 64, 64
PRECISION        = 8
CLOCK            = 1e-9

OUTPUT_CSV = 'outputs/comparison.csv'

WORKLOADS = [
    ('64x64x64',     64,   64,   64),
    ('128x128x128', 128,  128,  128),
    ('256x256x256', 256,  256,  256),
    ('512x512x512', 512,  512,  512),
]

# ===== assembly =====
def main():
    rows = []
    for name, M, N, K in WORKLOADS:

        ugemm = uGEMM_Arch(M, N, K, ARRAY_H, ARRAY_W,
                           acc_type="uNSADD", mul_type="uMUL-IS-unipolar",
                           clock=CLOCK, precision=PRECISION)
        rows.append({
            'workload': name, 'arch': 'uGEMM',
            'cycles':   ugemm.get_cycles(),
            'energy_pJ': ugemm.get_energy() * 1e12,
        })

        binmodel = BinarySystolic_Arch(M, N, K, ARRAY_H, ARRAY_W, PRECISION)
        rows.append({
            'workload': name, 'arch': 'Binary',
            'cycles':   binmodel.get_cycles(),
            'energy_pJ': binmodel.get_energy() * 1e12,
        })

        # usys = uSystolic_Arch(M, N, K, ARRAY_H, ARRAY_W,
        #                       clock=CLOCK, precision=PRECISION)
        # rows.append({'workload': name, 'arch': 'uSystolic',
        #              'cycles': usys.get_cycles(),
        #              'energy_pJ': usys.get_energy() * 1e12})
        #
        # camb = CambriconU_Arch(M, N, K, ARRAY_H, ARRAY_W,
        #                        clock=CLOCK, precision=PRECISION)
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