import energy as energy

class CambriconU_Arch:
    def __init__(self, m: int, n: int, k: int, clock: float, precision: int):
        self.m = m
        self.n = n
        self.k = k
        self.clock = clock
        self.freq = 1/clock
        self.l = 2**precision
        self.b = precision
        self.a = precision
    
    def weight_power(self):
        cmp = self.n * self.k * self.l * self.b * energy.__CMP
        wbit = (self.m - 1) * self.n * self.k * self.l * energy.__REG
        wsign = (self.m - 1) * self.n * self.k * self.b * energy.__REG
        rng = self.n * self.k * self.l * self.b * energy.__RNG
        
        return cmp + wbit + rng + wsign
    
    def input_power(self):
        cmp = self.m * self.k * self.l * self.b * energy.__CMP
        ibit = self.m * (self.n - 1) * self.k * self.l * energy.__REG
        isign = self.m * (self.n - 1) * self.k * self.b * energy.__REG
        rng = self.m * self.k * self.l * self.b * energy.__RNG
        
        return cmp + ibit + rng + isign
    
    def output_power(self):
        inc = self.m * self.n * self.k * (self.l / 2) * (self.a - 1) * energy.__RIM_INC
        reg = self.m * self.n * self.k * self.l * energy.__REG
        rim_read = self.m * self.n * self.a * energy.__RIM_RD
        bin_conv = self.m * self.n * self.skew2binary_power()
        
        return inc + rim_read + reg + bin_conv
    
    def pe_misc_power(self):
        prod = self.m * self.n * self.k * self.l * (energy.__NAND + energy.__NOR + energy.__OR + energy.__HA)
        sign = self.m * self.n * self.k * energy.__XOR
        
        return prod + sign
    
    def skew2binary_power(self):
        skew_reg = 2 * self.a * energy.__REG
        pc = self.a * energy.__PC
        add = (self.a/2) * energy.__ADD + self.a * energy.__BSHIFT
        sub = 2 * self.a * energy.__SUB
        lreg = self.a * energy.__REG
        
        return skew_reg + pc + add + sub + lreg
    """
    def peripheral_power(self):
        fifo = 2*self.cols*power.__FIFO*self.precision + self.rows*power.__FIFO*self.precision
        shift = self.cols*power.__SHIFT*self.precision
        
        return fifo + shift
    """
    
    def get_power(self):
        return self.input_power() + self.output_power() + self.weight_power() + self.pe_misc_power()# + self.peripheral_power()
    
    def get_energy(self):
        return self.get_power() * self.clock * self.get_cycles()
    
    def get_cycles(self):
        return self.m + 2*self.n + self.k * self.l - 2