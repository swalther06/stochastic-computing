import analytical_modeling.power as power

class uSystolic_Arch:
    def __init__(self, m: int, n: int, k: int, clock: float, precision: int):
        self.m = m
        self.n = n
        self.k = k
        self.clock = clock
        self.freq = 1/clock
        self.l = 2**precision
        self.b = precision
        self.a = precision # SET LATER BASED ON EARLY TERMINATION REQS
    
    def weight_power(self):
        cmp = self.m * self.n * self.k * self.l * self.b * power.__CMP
        wt_reg = self.m * self.n * (self.b) * power.__REG
        rng = self.m * self.k * self.b * power.__RNG
        rng_reg = self.m * (self.n - 1) * self.k * self.b * power.__REG
        
        return cmp + wt_reg + rng + rng_reg
    
    def input_power(self):
        cmp = self.n * self.k * self.l * self.b * power.__CMP
        inp_reg = self.n * self.k * (self.b) * power.__REG
        pe_reg = self.m * (self.n - 1) * self.k * self.l * power.__REG
        
        return cmp + inp_reg + pe_reg
    
    def output_power(self):
        acc = self.m * self.n * self.k * self.l * self.a * power.__INC
        add = self.m * self.n * self.k * self.a * power.__ADD
        reg = self.m * self.n * self.k * (self.l + 1) * self.a * power.__REG
        
        return acc + add + reg
    
    def pe_misc_power(self):
        prod = self.m * self.n * self.k * self.l * (power.__AND + power.__MUX + power.__SEL)
        sign = self.m * self.n * self.k * power.__XOR
        
        return prod + sign
    """
    def peripheral_power(self):
        fifo = 2 * self.n * self.b * power.__FIFO + self.m * self.b * power.__FIFO
        shift = self.n * self.b * power.__SHIFT
        
        return fifo + shift
    """
    
    def get_power(self):
        return self.input_power() + self.output_power() + self.weight_power() + self.pe_misc_power()# + self.peripheral_power()
    
    def get_energy(self):
        return self.get_power() * self.clock * self.get_cycles()
    
    def get_cycles(self):
        return self.m + self.n + self.k * (self.l + 1) - 2
        
        