import pandas as pd
from run_scalesim    import binary_via_scalesim
from run_usystolicsim import usystolic_via_sim
from binary_AM    import BinarySystolic_Arch
from uSystolic_AM import uSystolic_Arch
from energy import Energy

ARRAY_H, ARRAY_W = 64, 64
PRECISION        = 8
WORKLOADS = [('64', 64,64,64), ('128',128,128,128),
             ('256',256,256,256), ('512',512,512,512)]


def validate_binary():
    print("=== Binary vs SCALE-Sim ===")
    reports = binary_via_scalesim(WORKLOADS)
    compute = reports['compute']
    access  = reports['access']

    rows = []
    for (name, M, N, K), (_, crow), (_, arow) in zip(
            WORKLOADS, compute.iterrows(), access.iterrows()):
        model = BinarySystolic_Arch(M, N, K, ARRAY_H, ARRAY_W)
        m = model.summary()

        ss_sram_rd = int(arow['SRAM IFMAP Reads']) + int(arow['SRAM Filter Reads'])
        ss_sram_wr = int(arow['SRAM OFMAP Writes'])

        rows.append({
            'workload':      name,
            'model_cycles':  m['cycles'],
            'sim_cycles':    int(crow['Total Cycles']),
            'cycle_err_%':   100 * (m['cycles'] - int(crow['Total Cycles'])) / int(crow['Total Cycles']),
            'model_sram_rd': m['filter_sram_reads'] + m['ifmap_sram_reads'],
            'sim_sram_rd':   ss_sram_rd,
            'model_sram_wr': m['ofmap_sram_writes'],
            'sim_sram_wr':   ss_sram_wr,
        })

    print(pd.DataFrame(rows).to_string(index=False))


def validate_usystolic():
    print("\n=== uSystolic vs uSystolic-Sim (cycles) ===")
    sim_df = usystolic_via_sim(WORKLOADS, array_h=ARRAY_H, array_w=ARRAY_W,
                               precision=PRECISION)

    e = Energy(WORKLOADS[-1][1], WORKLOADS[-1][2], WORKLOADS[-1][3],
               array_h=ARRAY_H, array_w=ARRAY_W, precision=PRECISION)

    rows = []
    for (name, M, N, K), (_, srow) in zip(WORKLOADS, sim_df.iterrows()):
        model = uSystolic_Arch(M, N, K, ARRAY_H, ARRAY_W,
                               freq=1e9, precision=PRECISION, energy=e)
        sim_cycles   = int(srow['Cycles'])
        model_cycles = model.get_cycles()
        rows.append({
            'workload':     name,
            'model_cycles': model_cycles,
            'sim_cycles':   sim_cycles,
            'cycle_err_%':  100 * (model_cycles - sim_cycles) / sim_cycles,
        })

    print(pd.DataFrame(rows).to_string(index=False))


validate_binary()
validate_usystolic()