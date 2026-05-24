import energy as energy
from math import ceil

# Analytical model for uGEMM. Per the architecture workflow:
#   - PE is K-wide (one PE does a K-element dot product)
#   - operation runs in L cycles ("L latency")
#   - operation counts (KNL, MKL, MNL) are TOTALS over the L-cycle run

class uGEMM_Arch:
    # mul_type:  "uMUL-{ST,IS}-{unipolar,bipolar}"
    # acc_type:  "uSADD" | "uNSADD"
    def __init__(self, M, N, K, array_h, array_w,
                 acc_type, mul_type, clock, precision,
                 ifmap_sram_kB=1024, filter_sram_kB=1024, ofmap_sram_kB=1024):
        self.M = M            # workload dims
        self.N = N
        self.K = K
        self.H = array_h      # physical array dims (M-dim of array)
        self.W = array_w      # physical array dims (N-dim of array)

        self.acc_type  = acc_type
        self.mul_type  = mul_type
        self.clock     = clock
        self.precision = precision
        self.b = precision
        self.a = precision
        self.l = 2 ** precision

        # tiling: workload M,N tiled onto array H,W. K is K-wide within the PE.
        self.m_tiles   = ceil(M / array_h)
        self.n_tiles   = ceil(N / array_w)
        self.num_tiles = self.m_tiles * self.n_tiles

        self.pol_factor  = 2 if "bipolar" in mul_type else 1
        self.mode_factor = 2 if "IS" in mul_type else 1

        self.ifmap_sram = ifmap_sram_kB  * 1024
        self.filter_sram = filter_sram_kB * 1024
        self.ofmap_sram = ofmap_sram_kB  * 1024
    
    
    def filter_sram_reads(self):
        # K×N weights; each column-block of B reused across M-tiles.
        return self.K * self.N * self.m_tiles

    def ifmap_sram_reads(self):
        # M×K inputs; each row-block of A reused across N-tiles.
        return self.M * self.K * self.n_tiles

    def ofmap_sram_writes(self):
        # K accumulates fully in-PE -> each output written exactly once.
        return self.M * self.N

    def sram_summary(self):
        return {
            'filter_sram_reads': self.filter_sram_reads(),
            'ifmap_sram_reads':  self.ifmap_sram_reads(),
            'ofmap_sram_writes': self.ofmap_sram_writes(),
        }


    def weight_dyn_per_cycle(self):
        factor = self.pol_factor * self.mode_factor
        cmp = self.K * self.W * self.b * energy._CMP_DYN * factor
        rng = self.K * self.W * self.b * energy._RNG_DYN * factor
        return cmp + rng

    def input_dyn_per_cycle(self):
        cmp = self.H * self.K * self.b * energy._CMP_DYN
        rng = self.H * self.K * self.b * energy._RNG_DYN
        return cmp + rng

    def pe_compute_dyn_per_cycle(self):
        if "unipolar" in self.mul_type:
            return self.H * self.W * energy._AND_DYN
        else:
            return self.H * self.W * energy._XNOR_DYN

    def output_dyn_per_cycle(self):
        a_hw = self.a * self.H * self.W
        kp1  = (self.K + 1) * self.H * self.W
        if self.acc_type == "uSADD":
            return kp1 * energy._PC_DYN + kp1 * energy._ACC_DYN
        elif self.acc_type == "uNSADD":
            return (kp1 * energy._PC_DYN
                    + a_hw * energy._ACC_DYN + a_hw * energy._ACC_DYN
                    + a_hw * energy._SUB_DYN + a_hw * energy._CMP_DYN)
        else:
            raise ValueError(f"Unknown acc_type: {self.acc_type}")

    def get_PE_dyn_energy(self):
        # per-cycle dynamic energy of one tile, × cycles, × num_tiles
        per_cycle = (self.weight_dyn_per_cycle()
                     + self.input_dyn_per_cycle()
                     + self.pe_compute_dyn_per_cycle()
                     + self.output_dyn_per_cycle())
        return self.num_tiles * per_cycle * self.get_cycles_per_tile()

    def get_PE_leak_energy(self):
        execution_time = self.get_cycles() * self.clock
        num_pes = self.H * self.W
        factor  = self.pol_factor * self.mode_factor

        # uMUL: counter + bitstream generator(s) + multiply gate
        if "unipolar" in self.mul_type:
            mul_gate = energy._AND_LEAK
        else:
            mul_gate = energy._XNOR_LEAK
        umul_leak = (energy._CTR_LEAK
                    + (energy._RNG_LEAK + energy._CMP_LEAK) * factor
                    + mul_gate)

        # accumulate logic — PC scales with K
        pc_leak = self.K * energy._PC_LEAK          # K-wide parallel counter
        if self.acc_type == "uSADD":
            acc_leak = energy._ACC_LEAK
        elif self.acc_type == "uNSADD":
            acc_leak = energy._ACC_LEAK * 2 + energy._SUB_LEAK + energy._CMP_LEAK
        else:
            raise ValueError(f"Unknown acc_type: {self.acc_type}")

        per_pe_leak = umul_leak + pc_leak + acc_leak
        return num_pes * per_pe_leak * execution_time

    def get_mem_dyn_energy(self):
        filter_rd = self.filter_sram_reads() * energy._SRAM_READ_DYN
        ifmap_rd  = self.ifmap_sram_reads()  * energy._SRAM_READ_DYN
        ofmap_wr  = self.ofmap_sram_writes() * energy._SRAM_WRITE_DYN
        return filter_rd + ifmap_rd + ofmap_wr

    def get_mem_leak_energy(self):
        execution_time = self.get_cycles() * self.clock
        total_sram_kb = (self.filter_sram + self.ifmap_sram + self.ofmap_sram) / 1024
        return total_sram_kb * energy._SRAM_LEAK * execution_time

    def get_energy(self):
        return (self.get_PE_dyn_energy()
                + self.get_PE_leak_energy()
                + self.get_mem_dyn_energy()
                + self.get_mem_leak_energy())

    # ---- cycles ----
    def get_cycles_per_tile(self):
        # "L latency" — one tile completes in L cycles
        return self.l

    def get_cycles(self):
        return self.num_tiles * self.get_cycles_per_tile()

    def summary(self):
        return {
            'num_tiles': self.num_tiles,
            'cycles':    self.get_cycles(),
            'energy':    self.get_energy(),
        }
    