from energy import Energy


class CambriconU_Arch:
    def __init__(self, m: int, n: int, k: int, clock: float, precision: int,
                 energy: Energy):
        self.m = m
        self.n = n
        self.k = k
        self.clock = clock
        self.freq = 1 / clock
        self.l = 2 ** precision
        self.b = precision
        self.a = precision
        self.energy = energy

    def weight_power(self):
        e = self.energy
        cmp   = self.n * self.k * self.l * self.b * e.CMP_DYN
        wbit  = (self.m - 1) * self.n * self.k * self.l * e.REG_DYN
        wsign = (self.m - 1) * self.n * self.k * self.b * e.REG_DYN
        rng   = self.n * self.k * self.l * self.b * e.RNG_DYN
        return cmp + wbit + rng + wsign

    def input_power(self):
        e = self.energy
        cmp   = self.m * self.k * self.l * self.b * e.CMP_DYN
        ibit  = self.m * (self.n - 1) * self.k * self.l * e.REG_DYN
        isign = self.m * (self.n - 1) * self.k * self.b * e.REG_DYN
        rng   = self.m * self.k * self.l * self.b * e.RNG_DYN
        return cmp + ibit + rng + isign

    def output_power(self):
        e = self.energy
        inc      = self.m * self.n * self.k * (self.l / 2) * (self.a - 1) * e.RIM_INC_DYN
        reg      = self.m * self.n * self.k * self.l * e.REG_DYN
        rim_read = self.m * self.n * self.a * e.RIM_RD_DYN
        bin_conv = self.m * self.n * self.skew2binary_power()
        return inc + rim_read + reg + bin_conv

    def pe_misc_power(self):
        e = self.energy
        prod = self.m * self.n * self.k * self.l * (e.NAND_DYN + e.NOR_DYN + e.OR_DYN + e.HA_DYN)
        sign = self.m * self.n * self.k * e.XOR_DYN
        return prod + sign

    def skew2binary_power(self):
        e = self.energy
        skew_reg = 2 * self.a * e.REG_DYN
        pc       = self.a * e.PC_DYN
        add      = (self.a / 2) * e.ADD_DYN + self.a * e.BSHIFT_DYN
        sub      = 2 * self.a * e.SUB_DYN
        lreg     = self.a * e.REG_DYN
        return skew_reg + pc + add + sub + lreg

    """
    def peripheral_power(self):
        fifo  = 2*self.cols * e.FIFO_DYN * self.precision + self.rows * e.FIFO_DYN * self.precision
        shift = self.cols * e.SHIFT_DYN * self.precision
        return fifo + shift
    """

    def get_power(self):
        return (self.input_power() + self.output_power()
                + self.weight_power() + self.pe_misc_power())

    def get_energy(self):
        return self.get_power() * self.clock * self.get_cycles()

    def get_cycles(self):
        return self.m + 2 * self.n + self.k * self.l - 2
