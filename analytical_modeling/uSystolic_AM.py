from energy import Energy


class uSystolic_Arch:
    def __init__(self, M: int, N: int, K: int, clock: float, precision: int,
                 energy: Energy):
        self.m = M
        self.n = N
        self.k = K
        self.clock = clock
        self.freq = 1 / clock
        self.l = 2 ** precision
        self.b = precision
        self.a = precision  # SET LATER BASED ON EARLY TERMINATION REQS
        self.energy = energy

    def weight_power(self):
        e = self.energy
        cmp    = self.m * self.n * self.k * self.l * self.b * e.CMP_DYN
        wt_reg = self.m * self.n * self.b * e.REG_DYN
        rng    = self.m * self.k * self.b * e.RNG_DYN
        rng_reg = self.m * (self.n - 1) * self.k * self.b * e.REG_DYN
        return cmp + wt_reg + rng + rng_reg

    def input_power(self):
        e = self.energy
        cmp     = self.n * self.k * self.l * self.b * e.CMP_DYN
        inp_reg = self.n * self.k * self.b * e.REG_DYN
        pe_reg  = self.m * (self.n - 1) * self.k * self.l * e.REG_DYN
        return cmp + inp_reg + pe_reg

    def output_power(self):
        e = self.energy
        acc = self.m * self.n * self.k * self.l * self.a * e.INC_DYN
        add = self.m * self.n * self.k * self.a * e.ADD_DYN
        reg = self.m * self.n * self.k * (self.l + 1) * self.a * e.REG_DYN
        return acc + add + reg

    def pe_misc_power(self):
        e = self.energy
        prod = self.m * self.n * self.k * self.l * (e.AND_DYN + e.MUX_DYN + e.SEL_DYN)
        sign = self.m * self.n * self.k * e.XOR_DYN
        return prod + sign

    """
    def peripheral_power(self):
        fifo  = 2 * self.n * self.b * e.FIFO_DYN + self.m * self.b * e.FIFO_DYN
        shift = self.n * self.b * e.SHIFT_DYN
        return fifo + shift
    """

    def get_power(self):
        return (self.input_power() + self.output_power()
                + self.weight_power() + self.pe_misc_power())

    def get_energy(self):
        return self.get_power() * self.clock * self.get_cycles()

    def get_cycles(self):
        return self.m + self.n + self.k * (self.l + 1) - 2
