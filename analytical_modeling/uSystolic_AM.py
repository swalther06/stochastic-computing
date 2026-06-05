from math import ceil
from energy import Energy
from dataflow import sram_access_counts, to_physical_accesses


class uSystolic_Arch:
    DATAFLOW = 'ws'   # weight-stationary, same scheduling as binary

    # ---- Constructor --------------------------------------------------------

    def __init__(self, M: int, N: int, K: int,
                 array_h: int, array_w: int,
                 freq: float, precision: int,
                 energy: Energy,
                 ifmap_sram_kB=64, filter_sram_kB=64, ofmap_sram_kB=64,
                 include_memory=False,
                 use_usyssim_nums=False):
        self.M = M
        self.N = N
        self.K = K
        self.H = array_h
        self.W = array_w
        self.freq  = freq
        self.clock = 1.0 / freq
        self.precision = precision
        self.b = precision
        self.a = precision   # output resolution; can be reduced (see paper V-A)
        self.L = 2 ** (precision - 1)   # unipolar uMUL stream length
        self.energy = energy

        self.ifmap_sram  = ifmap_sram_kB  * 1024
        self.filter_sram = filter_sram_kB * 1024
        self.ofmap_sram  = ofmap_sram_kB  * 1024

        self.k_tiles = ceil(K / array_h)
        self.n_tiles = ceil(N / array_w)
        self.num_tiles = self.k_tiles * self.n_tiles
        self.include_memory = include_memory
        self.use_usyssim_nums = use_usyssim_nums

    # ---- helpers ------------------------------------------------------------

    def runtime(self):
        return self.get_cycles() * self.clock

    def _num_col0_pes(self):
        return self.H                 # leftmost column: one per row

    def _num_colc_pes(self):
        return self.H * (self.W - 1)  # all other columns

    def _num_total_pes(self):
        return self.H * self.W

    # ---- per-PE-type dynamic energy (one PE, one tile) ----------------------

    def _weight_col0_pe(self):
        e = self.energy
        cmp    = self.K * self.L * e.CMP_DYN     # C-W comparator
        wt_reg = self.b * e.REG_DYN                   # WABS + WSIGN
        rng    = self.K * self.L * e.RNG_DYN              # weight RNG (generation)
        return cmp + wt_reg + rng

    def _weight_colc_pe(self):
        e = self.energy
        cmp     = self.K * self.L * e.CMP_DYN    # C-W comparator (still present)
        wt_reg  = self.b * e.REG_DYN                  # WABS + WSIGN
        rng_reg = self.K * self.b * e.REG_DYN             # RREG reuse register
        return cmp + wt_reg + rng_reg

    def _input_col0_pe(self):
        e = self.energy
        cmp     = self.K * self.L * e.CMP_DYN    # C-I comparator
        inp_reg = self.K * self.b * e.REG_DYN         # IABS + ISIGN
        return cmp + inp_reg

    def _input_colc_pe(self):
        e = self.energy
        idff = 2 * self.K * self.L * e.REG_DYN            # IDFF reuse register
        return idff

    def _output_pe(self):
        e = self.energy
        acc = self.K * self.L * self.a * e.INC_DYN
        add = self.K * self.a * e.ADD_DYN
        reg = self.K * (self.L + 1) * self.a * e.REG_DYN
        return acc + add + reg

    def _misc_pe(self):
        e = self.energy
        prod = self.K * self.L * (e.AND_DYN + e.MUX_DYN + e.SEL_DYN)
        sign = self.K * e.XOR_DYN
        return prod + sign

    def pe_dyn_energy_usyssim(self):
        e = self.energy
        macs = self.M * self.N * self.K
        return macs * self.L * e.PE_USYS_INT8_DYN

    # ---- combined PE dynamic / leakage / total ------------------------------

    def get_PE_dyn_energy(self):
        """Total PE dynamic energy (J), per-PE-type weighted, scaled by num_tiles."""
        if self.use_usyssim_nums:
            return self.pe_dyn_energy_usyssim()
        col0 = self._num_col0_pes()  * (self._weight_col0_pe() + self._input_col0_pe())
        colc = self._num_colc_pes()  * (self._weight_colc_pe() + self._input_colc_pe())
        allp = self._num_total_pes() * (self._output_pe() + self._misc_pe())
        return self.num_tiles * (col0 + colc + allp)

    def get_PE_leak_energy(self):
        """Total PE leakage energy (J) = total leakage power * runtime.
        Only the H leftmost PEs carry RNG leakage (the dominant term)."""
        if self.use_usyssim_nums:
            num_pes = self._num_total_pes()
            return num_pes * self.energy.PE_USYS_INT8_LEAK * self.runtime()

        e = self.energy
        rt = self.runtime()
        col0_pe_leak = (2 * e.RNG_LEAK + 2 * e.CMP_LEAK)             # 2 RNG + C-W + C-I
        colc_pe_leak = (e.REG_LEAK + e.CMP_LEAK + e.REG_LEAK)       # RREG + C-W + IDFF
        all_pe_leak  = (4 * e.REG_LEAK                              # WABS/WSIGN/IABS/ISIGN
                        + e.ADD_LEAK + e.REG_LEAK                   # accumulate ADD + OREG
                        + e.AND_LEAK + e.MUX_LEAK + e.SEL_LEAK + e.XOR_LEAK)
        total_leak_power = (self._num_col0_pes()  * col0_pe_leak
                            + self._num_colc_pes() * colc_pe_leak
                            + self._num_total_pes() * all_pe_leak)
        return total_leak_power * rt

    def get_PE_energy(self):
        return self.get_PE_dyn_energy() + self.get_PE_leak_energy()

    # ---- Memory -------------------------------------------------------------

    def _elem_counts(self):
        return sram_access_counts(self.DATAFLOW, self.M, self.N, self.K,
                                  self.H, self.W)

    def filter_sram_reads(self):
        eb = max(1, self.precision // 8)
        return to_physical_accesses(self._elem_counts()['filter_reads'],
                                    self.energy.filter_access_bytes, eb)

    def ifmap_sram_reads(self):
        eb = max(1, self.precision // 8)
        return to_physical_accesses(self._elem_counts()['ifmap_reads'],
                                    self.energy.ifmap_access_bytes, eb)

    def ofmap_sram_writes(self):
        eb = max(1, self.precision // 8)
        return to_physical_accesses(self._elem_counts()['ofmap_writes'],
                                    self.energy.ofmap_access_bytes, eb)

    def sram_summary(self):
        return {
            'filter_sram_reads': self.filter_sram_reads(),
            'ifmap_sram_reads':  self.ifmap_sram_reads(),
            'ofmap_sram_writes': self.ofmap_sram_writes(),
        }

    def get_mem_energy(self):
        e = self.energy
        rt = self.runtime()
        dyn = (self.filter_sram_reads() * e.FILTER_SRAM_READ_DYN
               + self.ifmap_sram_reads()  * e.IFMAP_SRAM_READ_DYN
               + self.ofmap_sram_writes() * e.OFMAP_SRAM_WRITE_DYN)
        leak = rt * (e.IFMAP_SRAM_LEAK_W
                     + e.FILTER_SRAM_LEAK_W
                     + e.OFMAP_SRAM_LEAK_W)
        return dyn + leak

    # ---- Cycles -------------------------------------------------------------

    def get_cycles(self):
        mac = self.L + 1
        weight_load = self.H
        fill_drain  = self.H + self.W
        streaming   = self.M * mac
        per_tile    = weight_load + fill_drain + streaming
        return self.num_tiles * per_tile

    # ---- Total energy -------------------------------------------------------

    def get_energy(self):
        e = self.get_PE_energy()
        if self.include_memory:
            e += self.get_mem_energy()
        return e

    # ---- Summary ------------------------------------------------------------

    def summary(self):
        return {
            'num_tiles': self.num_tiles,
            'cycles':    self.get_cycles(),
            'energy':    self.get_energy(),
        }