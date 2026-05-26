from math import ceil
from energy import Energy


class uGEMM_Arch:
    # mul_type:  "uMUL-{ST,IS}-{unipolar,bipolar}"
    # acc_type:  "uSADD" | "uNSADD"
    def __init__(self, M, N, K, array_h, array_w,
                 acc_type, mul_type, clock, precision,
                 energy: Energy,
                 ifmap_sram_kB=1024, filter_sram_kB=1024, ofmap_sram_kB=1024):
        self.M = M
        self.N = N
        self.K = K
        self.H = array_h
        self.W = array_w

        self.acc_type  = acc_type
        self.mul_type  = mul_type
        self.clock     = clock
        self.precision = precision
        self.b = precision
        self.a = precision
        self.l = 2 ** precision
        self.energy = energy

        self.m_tiles   = ceil(M / array_h)
        self.n_tiles   = ceil(N / array_w)
        self.num_tiles = self.m_tiles * self.n_tiles

        self.pol_factor  = 2 if "bipolar" in mul_type else 1
        self.mode_factor = 2 if "IS" in mul_type else 1

        self.ifmap_sram  = ifmap_sram_kB  * 1024
        self.filter_sram = filter_sram_kB * 1024
        self.ofmap_sram  = ofmap_sram_kB  * 1024

    def filter_sram_reads(self):
        return self.K * self.N * self.m_tiles

    def ifmap_sram_reads(self):
        return self.M * self.K * self.n_tiles

    def ofmap_sram_writes(self):
        return self.M * self.N

    def sram_summary(self):
        return {
            'filter_sram_reads': self.filter_sram_reads(),
            'ifmap_sram_reads':  self.ifmap_sram_reads(),
            'ofmap_sram_writes': self.ofmap_sram_writes(),
        }

    def weight_dyn_per_cycle(self):
        e = self.energy
        factor = self.pol_factor * self.mode_factor
        cmp = self.K * self.W * self.b * e.CMP_DYN * factor
        rng = self.K * self.W * self.b * e.RNG_DYN * factor
        return cmp + rng

    def input_dyn_per_cycle(self):
        e = self.energy
        cmp = self.H * self.K * self.b * e.CMP_DYN
        rng = self.H * self.K * self.b * e.RNG_DYN
        return cmp + rng

    def pe_compute_dyn_per_cycle(self):
        e = self.energy
        if "unipolar" in self.mul_type:
            return self.H * self.W * e.AND_DYN
        else:
            return self.H * self.W * e.XNOR_DYN

    def output_dyn_per_cycle(self):
        e = self.energy
        a_hw = self.a * self.H * self.W
        kp1  = (self.K + 1) * self.H * self.W
        if self.acc_type == "uSADD":
            return kp1 * e.PC_DYN + kp1 * e.ACC_DYN
        elif self.acc_type == "uNSADD":
            return (kp1 * e.PC_DYN
                    + a_hw * e.ACC_DYN + a_hw * e.ACC_DYN
                    + a_hw * e.SUB_DYN + a_hw * e.CMP_DYN)
        else:
            raise ValueError(f"Unknown acc_type: {self.acc_type}")

    def get_PE_dyn_energy(self):
        per_cycle = (self.weight_dyn_per_cycle()
                     + self.input_dyn_per_cycle()
                     + self.pe_compute_dyn_per_cycle()
                     + self.output_dyn_per_cycle())
        return self.num_tiles * per_cycle * self.get_cycles_per_tile()

    def get_PE_leak_energy(self):
        e = self.energy
        execution_time = self.get_cycles() * self.clock
        num_pes = self.H * self.W
        factor  = self.pol_factor * self.mode_factor

        mul_gate = e.AND_LEAK if "unipolar" in self.mul_type else e.XNOR_LEAK
        umul_leak = (e.CTR_LEAK
                     + (e.RNG_LEAK + e.CMP_LEAK) * factor
                     + mul_gate)

        pc_leak = self.K * e.PC_LEAK
        if self.acc_type == "uSADD":
            acc_leak = e.ACC_LEAK
        elif self.acc_type == "uNSADD":
            acc_leak = e.ACC_LEAK * 2 + e.SUB_LEAK + e.CMP_LEAK
        else:
            raise ValueError(f"Unknown acc_type: {self.acc_type}")

        return num_pes * (umul_leak + pc_leak + acc_leak) * execution_time

    def get_mem_dyn_energy(self):
        e = self.energy
        filter_rd = self.filter_sram_reads() * e.SRAM_READ_DYN
        ifmap_rd  = self.ifmap_sram_reads()  * e.SRAM_READ_DYN
        ofmap_wr  = self.ofmap_sram_writes() * e.SRAM_WRITE_DYN
        return filter_rd + ifmap_rd + ofmap_wr

    def get_mem_leak_energy(self):
        execution_time = self.get_cycles() * self.clock
        total_sram_kb = (self.filter_sram + self.ifmap_sram + self.ofmap_sram) / 1024
        return total_sram_kb * self.energy.SRAM_LEAK * execution_time

    def get_energy(self):
        return (self.get_PE_dyn_energy()
                + self.get_PE_leak_energy()
                + self.get_mem_dyn_energy()
                + self.get_mem_leak_energy())

    def get_cycles_per_tile(self):
        return self.l

    def get_cycles(self):
        return self.num_tiles * self.get_cycles_per_tile()

    def summary(self):
        return {
            'num_tiles': self.num_tiles,
            'cycles':    self.get_cycles(),
            'energy':    self.get_energy(),
        }
