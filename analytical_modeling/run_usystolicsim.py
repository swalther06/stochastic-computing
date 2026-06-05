import os
import sys
import pandas as pd

_SIM_DIR = os.path.join(os.path.dirname(__file__), 'uSystolic-Sim')
sys.path.insert(0, _SIM_DIR)
import simArch.run_nets as run_nets


def _write_topology(workloads, precision, path):
    """Write a uSystolic-Sim GEMM topology CSV.

    Format (11 columns):
      Layer name, GEMM, ifmap_h, ifmap_w, filt_h, filt_w,
      channels, num_filters, stride_h, stride_w, mac_cycles

    GEMM C[M,N] = A[M,K] x B[K,N] maps to:
      ifmap_h=1, ifmap_w=M, filt_h=1, filt_w=1,
      channels=K, num_filters=N, stride=1
    mac_cycles = 2^(precision-1)  (unipolar uMUL stream length)
    """
    mac_cycles = 2 ** (precision - 1) + 1  # +1 for final accumulation cycle
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('Layer name, Type, IFMAP Height, IFMAP Width, '
                'Filter Height, Filter Width, Channels, Num Filter, '
                'Stride H, Stride W, MAC Cycles,\n')
        for name, M, N, K in workloads:
            f.write(f'{name}, GEMM, 1, {M}, 1, 1, {K}, {N}, 1, 1, {mac_cycles},\n')


def usystolic_via_sim(workloads, array_h=64, array_w=64, precision=8,
                      ifmap_sram_kB=1024, filter_sram_kB=1024, ofmap_sram_kB=1024):
    """Run uSystolic-Sim for all workloads.

    Returns a DataFrame with columns: Layer, Cycles, Utilization (%).
    """
    topo_path  = 'outputs/usystolic/gemm_topology.csv'
    out_prefix = 'outputs/usystolic/usystolic_run'
    os.makedirs('outputs/usystolic', exist_ok=True)

    _write_topology(workloads, precision, topo_path)

    run_nets.run_net(
        ifmap_sram_size=ifmap_sram_kB,
        filter_sram_size=filter_sram_kB,
        ofmap_sram_size=ofmap_sram_kB,
        array_h=array_h,
        array_w=array_w,
        data_flow='ws',
        word_size_bytes=max(1, precision // 8),
        topology_file=topo_path,
        net_name=out_prefix,
    )

    report_path = out_prefix + '_mac_util.csv'
    df = pd.read_csv(report_path)
    df.columns = df.columns.str.strip()
    return df
