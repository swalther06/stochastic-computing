# validate_binary_model.py
import pandas as pd
from compare import binary_via_scalesim
from binary_AM import BinaryUSystolic_Arch
# reuse your existing SCALE-Sim runner from compare_energy.py

ARRAY_H, ARRAY_W = 64, 64
WORKLOADS = [('64', 64,64,64), ('128',128,128,128),
             ('256',256,256,256), ('512',512,512,512)]

def validate():
    reports = binary_via_scalesim(WORKLOADS)     # now returns a dict
    compute = reports['compute']
    access  = reports['access']

    rows = []
    for (name, M, N, K), (_, crow), (_, arow) in zip(
            WORKLOADS, compute.iterrows(), access.iterrows()):
        model = BinaryUSystolic_Arch(M, N, K, ARRAY_H, ARRAY_W)
        m = model.summary()

        # SCALE-Sim SRAM reads (verify column names against your CSV header)
        ss_sram_rd = int(arow['SRAM IFMAP Reads']) + int(arow['SRAM Filter Reads'])
        ss_sram_wr = int(arow['SRAM OFMAP Writes'])  # if you want to validate writes too

        rows.append({
            'workload':       name,
            'model_cycles':   m['cycles'],
            'model_sram_rd':  m['filter_sram_reads'] + m['ifmap_sram_reads'],
            'model_sram_wr':  m['ofmap_sram_writes'],
            'ss_cycles':      int(crow['Total Cycles']),
            'ss_sram_rd':     ss_sram_rd,
            'ss_sram_wr':     ss_sram_wr,
        })

    df = pd.DataFrame(rows)
    #df['cycle_err_%'] = 100 * (df['model_cycles'] - df['ss_cycles']) / df['ss_cycles']
    #df['sram_rd_err_%']  = 100 * (df['model_sram_rd'] - df['ss_sram_rd']) / df['ss_sram_rd']
    #df['sram_wr_err_%'] = 100 * (df['model_sram_wr'] - df['ss_sram_wr']) / df['ss_sram_wr']
    print(df.to_string(index=False))

validate()