# binary_AM.py
from math import ceil
from dataflow import sram_access_counts, to_physical_accesses
from energy import Energy


class BinarySystolic_Arch:

    # ---- Constructor --------------------------------------------------------

    def __init__(self, M, N, K, array_h, array_w, precision=8, freq=1e9,
                 energy: Energy = None,
                 ifmap_sram_kB=1024, filter_sram_kB=1024, ofmap_sram_kB=1024,
                 include_memory=False):
        self.M, self.N, self.K = M, N, K
        self.H, self.W = array_h, array_w
        self.precision      = precision
        self.bytes_per_elem = max(1, precision // 8)
        self.freq  = freq
        self.clock = 1.0 / freq
        self.energy = energy or Energy(M, N, K,
                                       array_h=array_h, array_w=array_w,
                                       precision=precision, freq=freq,
                                       ifmap_sram_kB=ifmap_sram_kB,
                                       filter_sram_kB=filter_sram_kB,
                                       ofmap_sram_kB=ofmap_sram_kB)
        self.ifmap_sram   = ifmap_sram_kB  * 1024
        self.filter_sram  = filter_sram_kB * 1024
        self.ofmap_sram   = ofmap_sram_kB  * 1024

        self.k_tiles = ceil(K / array_h)
        self.n_tiles = ceil(N / array_w)
        self.num_tiles = self.k_tiles * self.n_tiles
        self.include_memory = include_memory

    # ---- PE: dynamic + leakage combined -------------------------------------

    def get_PE_energy(self):
        e = self.energy
        macs = self.M * self.N * self.K
        num_pes = self.H * self.W
        runtime = self.get_cycles() * self.clock

        dyn  = macs * (e.PE_BINARY_INT8_DYN)
        leak = num_pes * (e.PE_BINARY_INT8_LEAK) * runtime
        return dyn + leak

    # ---- Memory: dynamic + leakage combined ---------------------------------

    def _sram_elem_counts(self):
        return sram_access_counts('ws', self.M, self.N, self.K, self.H, self.W)

    def filter_sram_reads(self):
        return self._sram_elem_counts()['filter_reads']

    def ifmap_sram_reads(self):
        return self._sram_elem_counts()['ifmap_reads']

    def ofmap_sram_writes(self):
        return self._sram_elem_counts()['ofmap_writes']

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

    def get_mem_energy(self):
        e  = self.energy
        eb = self.bytes_per_elem
        c  = self._sram_elem_counts()
        runtime = self.get_cycles() * self.clock

        phys_filter = to_physical_accesses(c['filter_reads'], e.filter_access_bytes, eb)
        phys_ifmap  = to_physical_accesses(c['ifmap_reads'],  e.ifmap_access_bytes,  eb)
        phys_ofmap  = to_physical_accesses(c['ofmap_writes'], e.ofmap_access_bytes,  eb)
        dyn = (phys_filter * e.FILTER_SRAM_READ_DYN
               + phys_ifmap  * e.IFMAP_SRAM_READ_DYN
               + phys_ofmap  * e.OFMAP_SRAM_WRITE_DYN)

        # *_SRAM_LEAK_W are absolute leakage power (W) per SRAM. Sum * runtime.
        leak = runtime * (e.IFMAP_SRAM_LEAK_W
                          + e.FILTER_SRAM_LEAK_W
                          + e.OFMAP_SRAM_LEAK_W)
        return dyn + leak

    # ---- Cycles -------------------------------------------------------------

    def get_cycles(self):
        weight_load = self.H
        fill_drain  = self.H + self.W
        streaming   = self.M
        per_tile    = weight_load + fill_drain + streaming - 2
        return self.num_tiles * per_tile - 1

    # ---- Total energy -------------------------------------------------------

    def get_energy(self):
        e = self.get_PE_energy()
        if self.include_memory:
            e += self.get_mem_energy()
        return e

    # ---- Summary ------------------------------------------------------------

    def summary(self):
        return {
            'cycles':            self.get_cycles(),
            'energy':            self.get_energy(),
            'filter_sram_reads': self.filter_sram_reads(),
            'ifmap_sram_reads':  self.ifmap_sram_reads(),
            'ofmap_sram_writes': self.ofmap_sram_writes(),
            'dram_filter_reads': self.dram_filter_reads(),
            'dram_ifmap_reads':  self.dram_ifmap_reads(),
            'dram_ofmap_writes': self.dram_ofmap_writes(),
        }