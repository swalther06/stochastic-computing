from math import ceil
from dataflow import sram_access_counts, to_physical_accesses
from energy import Energy


class uGEMM_Arch:
    # mul_type:  "uMUL-{ST,IS}-{unipolar,bipolar}"
    # acc_type:  "uSADD" | "uNSADD"

    # ---- Constructor --------------------------------------------------------

    def __init__(self, M, N, K, array_h, array_w,
                 acc_type, mul_type, freq, precision,
                 energy: Energy,
                 ifmap_sram_kB=1024, filter_sram_kB=1024, ofmap_sram_kB=1024,
                 include_memory=False):
        self.M = M
        self.N = N
        self.K = K
        self.H = array_h
        self.W = array_w

        self.acc_type       = acc_type
        self.mul_type       = mul_type
        self.freq           = freq
        self.clock          = 1.0 / freq
        self.precision      = precision
        self.bytes_per_elem = max(1, precision // 8)
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
        self.include_memory = include_memory

    # ---- per-component DYNAMIC energy per cycle (J/cycle) -------------------

    def _weight_dyn_per_cycle(self):
        e = self.energy
        factor = self.pol_factor * self.mode_factor
        return (self.K * self.W * e.CMP_DYN * factor
                + self.K * self.W * e.RNG_DYN * factor)

    def _input_dyn_per_cycle(self):
        e = self.energy
        return (self.H * self.K * e.CMP_DYN
                + self.H * self.K * e.RNG_DYN)

    def _compute_dyn_per_cycle(self):
        e = self.energy
        if "unipolar" in self.mul_type:
            return self.H * self.W * e.AND_DYN
        return self.H * self.W * e.XNOR_DYN

    def _output_dyn_per_cycle(self):
        e = self.energy
        num_pes = self.H * self.W
        if self.acc_type == "uSADD":
            return num_pes * (e.PC_DYN + e.ACC_DYN)
        elif self.acc_type == "uNSADD":
            return (num_pes * e.PC_DYN
                    + num_pes * e.ACC_DYN * 3
                    + num_pes * e.SUB_DYN
                    + num_pes * e.CMP_DYN)
        raise ValueError(f"Unknown acc_type: {self.acc_type}")

    def _dyn_per_cycle(self):
        """Total PE dynamic energy per cycle (J)."""
        return (self._weight_dyn_per_cycle()
                + self._input_dyn_per_cycle()
                + self._compute_dyn_per_cycle()
                + self._output_dyn_per_cycle())

    # ---- per-component LEAKAGE power (W) ------------------------------------

    def _weight_leak_power(self):
        e = self.energy
        factor = self.pol_factor * self.mode_factor
        return self.K * self.W * (e.RNG_LEAK + e.CMP_LEAK) * factor

    def _input_leak_power(self):
        e = self.energy
        return self.H * self.K * (e.RNG_LEAK + e.CMP_LEAK)

    def _compute_leak_power(self):
        e = self.energy
        if "unipolar" in self.mul_type:
            return self.H * self.W * e.AND_LEAK
        return self.H * self.W * e.XNOR_LEAK

    def _output_leak_power(self):
        e = self.energy
        num_pes = self.H * self.W
        if self.acc_type == "uSADD":
            return num_pes * (e.PC_LEAK + e.ACC_LEAK)
        elif self.acc_type == "uNSADD":
            return (num_pes * e.PC_LEAK
                    + num_pes * e.ACC_LEAK * 3
                    + num_pes * e.SUB_LEAK
                    + num_pes * e.CMP_LEAK)
        raise ValueError(f"Unknown acc_type: {self.acc_type}")

    def _leak_power(self):
        """Total PE leakage power (W)."""
        return (self._weight_leak_power()
                + self._input_leak_power()
                + self._compute_leak_power()
                + self._output_leak_power())

    # ---- per-tile energy ----------------------------------------------------

    def get_PE_dyn_energy_per_tile(self):
        """PE dynamic energy for ONE tile (J) = per-cycle dyn * L cycles."""
        return self._dyn_per_cycle() * self.get_cycles_per_tile()

    def get_PE_leak_energy_per_tile(self):
        """PE leakage energy for ONE tile (J) = leak power * time per tile."""
        time_per_tile = self.get_cycles_per_tile() * self.clock
        return self._leak_power() * time_per_tile

    # ---- PE energy: dynamic and leakage SEPARATE, each * num_tiles ----------

    def get_PE_dyn_energy(self):
        """Total PE dynamic energy (J) = num_tiles * per-tile dynamic."""
        return self.num_tiles * self.get_PE_dyn_energy_per_tile()

    def get_PE_leak_energy(self):
        """Total PE leakage energy (J) = num_tiles * per-tile leakage."""
        return self.num_tiles * self.get_PE_leak_energy_per_tile()

    def get_PE_energy(self):
        """Total PE energy (J) = dynamic + leakage."""
        return self.get_PE_dyn_energy() + self.get_PE_leak_energy()

    # ---- Memory -------------------------------------------------------------

    def _sram_elem_counts(self):
        return sram_access_counts('ugemm', self.M, self.N, self.K, self.H, self.W)

    def filter_sram_reads(self):
        return self._sram_elem_counts()['filter_reads']

    def ifmap_sram_reads(self):
        return self._sram_elem_counts()['ifmap_reads']

    def ofmap_sram_writes(self):
        return self._sram_elem_counts()['ofmap_writes']

    def sram_summary(self):
        return {
            'filter_sram_reads': self.filter_sram_reads(),
            'ifmap_sram_reads':  self.ifmap_sram_reads(),
            'ofmap_sram_writes': self.ofmap_sram_writes(),
        }

    def get_mem_dyn_energy(self):
        """Memory dynamic energy (J). Access-count based."""
        e  = self.energy
        eb = self.bytes_per_elem
        c  = self._sram_elem_counts()
        phys_filter = to_physical_accesses(c['filter_reads'], e.filter_access_bytes, eb)
        phys_ifmap  = to_physical_accesses(c['ifmap_reads'],  e.ifmap_access_bytes,  eb)
        phys_ofmap  = to_physical_accesses(c['ofmap_writes'], e.ofmap_access_bytes,  eb)
        return (phys_filter * e.FILTER_SRAM_READ_DYN
                + phys_ifmap  * e.IFMAP_SRAM_READ_DYN
                + phys_ofmap  * e.OFMAP_SRAM_WRITE_DYN)

    def get_mem_leak_energy(self):
        """Memory leakage energy (J) = sum(SRAM leak power) * runtime."""
        e = self.energy
        leak_power = (e.IFMAP_SRAM_LEAK_W + e.FILTER_SRAM_LEAK_W + e.OFMAP_SRAM_LEAK_W)
        return leak_power * self.get_runtime()

    def get_mem_energy(self):
        """Total memory energy (J) = dynamic (access) + leakage (power*runtime)."""
        return self.get_mem_dyn_energy() + self.get_mem_leak_energy()

    # ---- Cycles / time ------------------------------------------------------

    def get_cycles_per_tile(self):
        return self.l

    def get_cycles(self):
        return self.num_tiles * self.get_cycles_per_tile()

    def get_runtime(self):
        """Wall-clock runtime (s) = total cycles * clock period."""
        return self.get_cycles() * self.clock

    def get_num_macs(self):
        return self.M * self.N * self.K

    def get_cycles_per_mac(self):
        """cycles/MAC = total cycles / MAC count (~L for unary, 1 for binary)."""
        macs = self.get_num_macs()
        return self.get_cycles() / macs if macs > 0 else 0.0

    # ---- Total energy -------------------------------------------------------

    def get_energy(self):
        """Total energy (J) = PE energy [+ memory]."""
        e = self.get_PE_energy()
        if self.include_memory:
            e += self.get_mem_energy()
        return e

    def get_energy_per_mac(self):
        """Energy per MAC (J) = total energy / #MAC."""
        macs = self.get_num_macs()
        return self.get_energy() / macs if macs > 0 else 0.0

    # ---- Summary ------------------------------------------------------------

    def summary(self):
        return {
            'num_tiles':       self.num_tiles,
            'cycles':          self.get_cycles(),
            'runtime_s':       self.get_runtime(),
            'cycles_per_mac':  self.get_cycles_per_mac(),
            'PE_dyn_energy_J': self.get_PE_dyn_energy(),
            'PE_leak_energy_J':self.get_PE_leak_energy(),
            'energy_J':        self.get_energy(),
            'energy_per_mac':  self.get_energy_per_mac(),
        }