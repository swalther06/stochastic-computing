import os
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt

_GRAPH_DIR = os.path.join(os.path.dirname(__file__), 'graphs')

_CATS   = ['inputs', 'weights', 'output', 'memory']
_LABELS = ['Inputs', 'Weights', 'Compute/Output', 'Memory']
_COLORS = ['#4C72B0', '#DD8452', '#55A868', '#C44E52']


def plot_energy_breakdowns(breakdown_rows, workload_order, arch_order):
    """Generate one 100% stacked bar chart per workload.

    breakdown_rows: list of dicts with keys 'workload', 'arch',
                    'inputs', 'weights', 'output', 'memory'
    workload_order: list of workload names controlling chart order
    arch_order:     list of arch names controlling bar order within each chart
    """
    os.makedirs(_GRAPH_DIR, exist_ok=True)

    by_workload = defaultdict(dict)
    for row in breakdown_rows:
        by_workload[row['workload']][row['arch']] = {c: row[c] for c in _CATS}

    for workload in workload_order:
        arch_data = by_workload.get(workload, {})
        archs = [a for a in arch_order if a in arch_data]
        if not archs:
            continue

        pcts = {cat: [] for cat in _CATS}
        for arch in archs:
            d = arch_data[arch]
            total = sum(d[c] for c in _CATS)
            for cat in _CATS:
                pcts[cat].append(100.0 * d[cat] / total if total > 0 else 0.0)

        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(archs))
        bottom = np.zeros(len(archs))

        for cat, color, label in zip(_CATS, _COLORS, _LABELS):
            vals = np.array(pcts[cat])
            ax.bar(x, vals, bottom=bottom, color=color, label=label, width=0.5)
            for xi, (v, b) in enumerate(zip(vals, bottom)):
                if v < 1.0:
                    pass
                elif v >= 5.0:
                    ax.text(xi, b + v / 2, f'{v:.1f}%',
                            ha='center', va='center',
                            fontsize=8, color='black', fontweight='bold')
                else:
                    ax.annotate(f'{v:.1f}%',
                                xy=(xi + 0.25, b + v / 2),
                                xytext=(xi + 0.45, b + v / 2),
                                ha='left', va='center',
                                fontsize=7, color='black', fontweight='bold',
                                arrowprops=dict(arrowstyle='-', color='black', lw=0.7))
            bottom += vals

        ax.set_xlim(-0.5, len(archs) - 0.5 + 0.9)
        ax.set_xticks(x)
        ax.set_xticklabels(archs)
        ax.set_ylabel('Energy (%)')
        ax.set_ylim(0, 100)
        ax.set_title(f'Energy Breakdown — {workload}')
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), borderaxespad=0)

        out_path = os.path.join(_GRAPH_DIR, f'energy_breakdown_{workload}.png')
        fig.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f'[plot] Saved {out_path}')
