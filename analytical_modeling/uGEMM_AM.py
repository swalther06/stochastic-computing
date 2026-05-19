import analytical_modeling.power as power

# Analytical model for uGEMM MAC architecture

class uGEMM_Arch:
    # --- mul_type:  "uMUL-{ST,IS}-{unipolar,bipolar}"
    # --- acc_type:  "uSADD" | "uNSADD"
    def __init__(self, m, k, n, acc_type, mul_type, clock, precision):
        self.m         = m
        self.k         = k
        self.n         = n
        self.acc_type  = acc_type
        self.mul_type  = mul_type
        self.clock     = clock
        self.freq      = 1 / clock
        self.precision = precision
        self.b = precision
        self.l = 2** precision
        self.a = precision

        # Bipolar uMUL is a *decomposed* XNOR: two gated Sobol generators
        # (one on Sin,0=1, one on Sin,0=0) OR'd together. -> 2x internal gen.
        self.pol_factor = 2 if "bipolar" in mul_type else 1

        # uMUL-ST: weight prestored in counter; only the internal gated G runs.
        # uMUL-IS: weight arrives as a stream, which itself had to be generated
        #          upstream -- so we pay for *both* external gen and the
        #          internal counter+G path. -> 2x.
        self.mode_factor = 2 if "IS" in mul_type else 1

    def weight_power(self):
        factor = self.pol_factor * self.mode_factor
        cmp = self.k * self.n * self.l * self.b * power.__CMP * factor
        rng = self.k * self.n * self.l * self.b * power.__RNG * factor
        return cmp + rng

    def input_power(self):
        cmp = self.m * self.k * self.l * self.b * power.__CMP
        rng = self.m * self.k * self.l * self.b * power.__RNG
        return cmp + rng

    def pe_misc_power(self):
        if "unipolar" in self.mul_type:
            mul = self.m * self.n * self.l * self.k * power.__AND
        else:  # bipolar
            mul = self.m * self.n * self.l * self.k * power.__XNOR
        return mul

    def output_power(self):
        mnl    = self.m * self.n * self.l
        kp1mnl = (self.k + 1) * mnl       # PC: (K+1) input wires
        a_mnl  = self.a * mnl             # A-bit ops downstream of PC

        if self.acc_type == "uSADD":
            pc  = kp1mnl * power.__PC
            add = kp1mnl * power.__ACC
            return pc + add

        elif self.acc_type == "uNSADD":
            pc      = kp1mnl * power.__PC
            acc_in  = a_mnl * power.__ACC
            acc_off = a_mnl * power.__ACC
            sub     = a_mnl * power.__SUB
            cmp     = a_mnl * power.__CMP
            return pc + acc_in + acc_off + sub + cmp

        else:
            raise ValueError(f"Unknown acc_type: {self.acc_type}")

    # =========================================================
    # Totals
    # =========================================================
    def get_power(self):
        return self.weight_power() + self.input_power() + self.pe_compute_power() + self.output_power()
    
    def get_cycles(self):
        return self.l

    def get_energy(self):
        return self.get_power() * self.get_cycles() * self.clock
    
    