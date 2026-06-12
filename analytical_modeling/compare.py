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
from plot import plot_energy_breakdowns

OUTPUT_CSV = 'outputs/comparison.csv'

WORKLOADS = [
    ('64x64x64',     64,   64,   64),
    ('128x128x128', 128,  128,  128),
    ('256x256x256', 256,  256,  256),
    ('512x512x512', 512,  512,  512),
    ('2048x2048x2048', 2048, 2048, 2048),
    ('65536x65536x65536', 65536, 65536, 65536),
    ('128x512x1024', 1024, 512, 256),
    ('256x64x4096', 1024, 512, 256),
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
    p.add_argument('--no-ugemm', action='store_true', dest='no_ugemm',
                   help='Skip uGEMM-specific synthesis targets (pc/acc/min); '
                        'allows synthesis to run once for fixed precision/array params')
    p.add_argument('--cacti', action='store_true',
                   help='Run CACTI to populate SRAM read/write/leakage energy values')
    p.add_argument('--memory', choices=['t', 'f'], default='f',
                   help='Include SRAM memory energy (t=yes, f=no; default: f)')
    p.add_argument('--graph', choices=['t', 'f'], default='f',
                   help='Save 100%% stacked energy-breakdown bar charts (t=yes, f=no; default: f)')
    return p.parse_args()


def main():
    args = parse_args()

    workloads = WORKLOADS
    if args.M is not None or args.N is not None or args.K is not None:
        M = args.M or WORKLOADS[0][1]
        N = args.N or WORKLOADS[0][2]
        K = args.K or WORKLOADS[0][3]
        workloads = [(f'{M}x{N}x{K}', M, N, K)]

    include_memory = args.memory == 't'
    if include_memory:
        print('Memory: included')
    else:
        print('Memory: not included (pass --memory t or MEMORY=t to include)')

    rows = []
    breakdown_rows = []
    synth_ref: 'Energy | None' = None
    synth_attrs: set = set()
    for name, M, N, K in workloads:
        e = Energy(M, N, K,
                   array_h=args.array_h, array_w=args.array_w,
                   precision=args.precision, freq=args.frequency,
                   ifmap_sram_kB=IFMAP_SRAM_KB,
                   filter_sram_kB=FILTER_SRAM_KB,
                   ofmap_sram_kB=OFMAP_SRAM_KB)
        if args.synthesize:
            if args.no_ugemm:
                if synth_ref is None:
                    e.synthesize(include_ugemm=False)
                    synth_ref = e
                    synth_attrs = {a
                                   for *_, da, la in e._synthesis_targets(include_ugemm=False)
                                   for a in (da, la)}
                else:
                    for attr in synth_attrs:
                        setattr(e, attr, getattr(synth_ref, attr))
            else:
                if synth_ref is None:
                    e.synthesize(include_ugemm=True)
                    synth_ref = e
                    synth_attrs = {a
                                   for *_, da, la in e._synthesis_targets(include_ugemm=False)
                                   for a in (da, la)}
                else:
                    for attr in synth_attrs:
                        setattr(e, attr, getattr(synth_ref, attr))
                    e.synthesize(ugemm_only=True)
        if args.cacti:
            e.run_cacti()
        if not args.synthesize and not args.cacti:
            print(f'[{name}] Using cached energy values (pass --synthesize and/or --cacti to refresh)')
        

        binmodel = BinarySystolic_Arch(M, N, K, args.array_h, args.array_w,
                                       precision=args.precision, freq=args.frequency, energy=e,
                                       include_memory=include_memory, ifmap_sram_kB=IFMAP_SRAM_KB, 
                                       filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)
        rows.append({
            'workload': name, 'arch': 'Binary',
            'cycles':   binmodel.get_cycles(),
            'energy_pJ': binmodel.get_energy() * 1e12,
            'pe_pct':   binmodel.get_pe_energy_pct(),
        })
        breakdown_rows.append({'workload': name, 'arch': 'Binary',
                                **binmodel.get_energy_breakdown()})

        ugemm = uGEMM_Arch(M, N, K,
                acc_type="uNSADD", mul_type="uMUL-IS-unipolar",
                freq=args.frequency, precision=args.precision, energy=e,
                include_memory=include_memory, ifmap_sram_kB=IFMAP_SRAM_KB,
                filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)

        if (not args.no_ugemm):
            rows.append({
                'workload': name, 'arch': 'uGEMM',
                'cycles':   ugemm.get_cycles(),
                'energy_pJ': ugemm.get_energy() * 1e12,
                'pe_pct':   ugemm.get_pe_energy_pct(),
            })
            breakdown_rows.append({'workload': name, 'arch': 'uGEMM',
                                    **ugemm.get_energy_breakdown()})

        usys = uSystolic_Arch(M, N, K, args.array_h, args.array_w,
                              freq=args.frequency, precision=args.precision,
                              energy=e, include_memory=include_memory, ifmap_sram_kB=IFMAP_SRAM_KB,
                              filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)
        rows.append({
            'workload': name, 'arch': 'uSystolic',
            'cycles':   usys.get_cycles(),
            'energy_pJ': usys.get_energy() * 1e12,
            'pe_pct':   usys.get_pe_energy_pct(),
        })
        breakdown_rows.append({'workload': name, 'arch': 'uSystolic',
                                **usys.get_energy_breakdown()})

        camb = CambriconU_Arch(M, N, K, args.array_h, args.array_w,
                              freq=args.frequency, precision=args.precision,
                              energy=e, include_memory=include_memory, ifmap_sram_kB=IFMAP_SRAM_KB,
                              filter_sram_kB=FILTER_SRAM_KB, ofmap_sram_kB=OFMAP_SRAM_KB)
        rows.append({'workload': name, 'arch': 'CambriconU',
                      'cycles': camb.get_cycles(),
                      'energy_pJ': camb.get_energy() * 1e12,
                      'pe_pct': camb.get_pe_energy_pct()})
        breakdown_rows.append({'workload': name, 'arch': 'CambriconU',
                                **camb.get_energy_breakdown()})

    df = pd.DataFrame(rows)
    workload_order = [w[0] for w in workloads]

    print("\nEnergy (pJ):")
    print(df.pivot(index='workload', columns='arch', values='energy_pJ').reindex(workload_order))
    print("\nCycles:")
    print(df.pivot(index='workload', columns='arch', values='cycles').reindex(workload_order))
    print("\nPE Energy (% of total):")
    print(df.pivot(index='workload', columns='arch', values='pe_pct').reindex(workload_order).map(lambda x: f'{x:.1f}%' if pd.notna(x) else 'N/A'))

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nWrote results to {OUTPUT_CSV}")

    if args.graph == 't':
        arch_order = ['Binary', 'uGEMM', 'uSystolic', 'CambriconU']
        plot_energy_breakdowns(breakdown_rows, workload_order, arch_order)


if __name__ == '__main__':
    main()
