import energy as energy

class uSystolic_Arch:
    def _init_(self, m: int, n: int, k: int, clock: float, precision: int):
        self.m = m
        self.n = n
        self.k = k
        self.clock = clock
        self.freq = 1/clock
        self.l = 2**precision
        self.b = precision
        self.a = precision # SET LATER BASED ON EARLY TERMINATION REQS
    
    def weight_power(self):
        cmp = self.m * self.n * self.k * self.l * self.b * energy._CMP_DYN
        wt_reg = self.m * self.n * (self.b) * energy._REG_DYN
        rng = self.m * self.k * self.b * energy._RNG_DYN
        rng_reg = self.m * (self.n - 1) * self.k * self.b * energy._REG
        
        return cmp + wt_reg + rng + rng_reg
    
    def input_power(self):
        cmp = self.n * self.k * self.l * self.b * energy._CMP
        inp_reg = self.n * self.k * (self.b) * energy._REG
        pe_reg = self.m * (self.n - 1) * self.k * self.l * energy._REG
        
        return cmp + inp_reg + pe_reg
    
    def output_power(self):
        acc = self.m * self.n * self.k * self.l * self.a * energy._INC
        add = self.m * self.n * self.k * self.a * energy._ADD
        reg = self.m * self.n * self.k * (self.l + 1) * self.a * energy._REG
        
        return acc + add + reg
    
    def pe_misc_power(self):
        prod = self.m * self.n * self.k * self.l * (energy._AND + energy._MUX + energy._SEL)
        sign = self.m * self.n * self.k * energy._XOR
        
        return prod + sign
    """
    def peripheral_power(self):
        fifo = 2 * self.n * self.b * power._FIFO + self.m * self.b * power._FIFO
        shift = self.n * self.b * power._SHIFT
        
        return fifo + shift
    """
    
    def get_power(self):
        return self.input_power() + self.output_power() + self.weight_power() + self.pe_misc_power()# + self.peripheral_power()
    
    def get_energy(self):
        return self.get_power() * self.clock * self.get_cycles()
    
    def get_cycles(self):
        return self.m + self.n + self.k * (self.l + 1) - 2
        
        