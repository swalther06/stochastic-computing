# binary_usystolic_AM.py
from math import ceil
from energy import Energy


class BinarySystolic_Arch:
    """Analytical model of a bit-parallel weight-stationary systolic array.
    This is uSystolic's binary baseline: same dataflow, 1 cycle per MAC."""

    def __init__(self, M, N, K, array_h, array_w, precision=8, clock=1e-9,
                 energy: Energy = None,
                 ifmap_sram_kB=1024, filter_sram_kB=1024, ofmap_sram_kB=1024):
        self.M, self.N, self.K = M, N, K
        self.H, self.W = array_h, array_w
        self.bytes_per_elem = precision / 8.0
        self.clock = clock
        self.energy = energy or Energy(M, N, K, precision, clock)
        self.ifmap_sram   = ifmap_sram_kB  * 1024
        self.filter_sram  = filter_sram_kB * 1024
        self.ofmap_sram   = ofmap_sram_kB  * 1024

        self.k_tiles = ceil(K / array_h)
        self.n_tiles = ceil(N / array_w)
        self.num_tiles = self.k_tiles * self.n_tiles

    # ---- cycles ----
    def get_cycles(self):
        weight_load = self.H
        fill_drain  = self.H + self.W
        streaming   = self.M
        per_tile    = weight_load + fill_drain + streaming - 2
        return self.num_tiles * per_tile - 1

    # ---- SRAM accesses ----
    def filter_sram_reads(self):
        return self.K * self.N

    def ifmap_sram_reads(self):
        return self.M * self.K * self.n_tiles

    def ofmap_sram_writes(self):
        return self.M * self.N * self.k_tiles

    # ---- DRAM accesses ----
    def _fits(self, n_elems, sram_bytes):
        return n_elems * self.bytes_per_elem <= sram_bytes

    def dram_filter_reads(self):
        if self._fits(self.K * self.N, self.filter_sram):
            return self.K * self.N
        return self.K * self.N * self.n_tiles

    def dram_ifmap_reads(self):
        if self._fits(self.M * self.K, self.ifmap_sram):
            return self.M * self.K
        return self.M * self.K * self.n_tiles

    def dram_ofmap_writes(self):
        return self.M * self.N

    def summary(self):
        return {
            'cycles':            self.get_cycles(),
            'filter_sram_reads': self.filter_sram_reads(),
            'ifmap_sram_reads':  self.ifmap_sram_reads(),
            'ofmap_sram_writes': self.ofmap_sram_writes(),
            'dram_filter_reads': self.dram_filter_reads(),
            'dram_ifmap_reads':  self.dram_ifmap_reads(),
            'dram_ofmap_writes': self.dram_ofmap_writes(),
        }

    def get_PE_dyn_energy(self):
        macs = self.M * self.N * self.K
        return macs * self.energy.MAC_BINARY_INT8_DYN

    def get_PE_leak_energy(self):
        execution_time = self.get_cycles() * self.clock
        num_pes = self.H * self.W
        return num_pes * execution_time * self.energy.MAC_BINARY_INT8_LEAK

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
        return (self.get_PE_dyn_energy() + self.get_PE_leak_energy()
                + self.get_mem_dyn_energy() + self.get_mem_leak_energy())
