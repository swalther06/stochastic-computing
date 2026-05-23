import energy as energy
from math import ceil

# Analytical model for uGEMM. Per the architecture workflow:
#   - PE is K-wide (one PE does a K-element dot product)
#   - operation runs in L cycles ("L latency")
#   - operation counts (KNL, MKL, MNL) are TOTALS over the L-cycle run

class uGEMM_Arch:
    # mul_type:  "uMUL-{ST,IS}-{unipolar,bipolar}"
    # acc_type:  "uSADD" | "uNSADD"
    def __init__(self, M, N, K, array_h, array_w,
                 acc_type, mul_type, clock, precision):
        self.M = M            # workload dims
        self.N = N
        self.K = K
        self.H = array_h      # physical array dims (M-dim of array)
        self.W = array_w      # physical array dims (N-dim of array)

        self.acc_type  = acc_type
        self.mul_type  = mul_type
        self.clock     = clock
        self.precision = precision
        self.b = precision
        self.a = precision
        self.l = 2 ** precision

        # tiling: workload M,N tiled onto array H,W. K is K-wide within the PE.
        self.m_tiles   = ceil(M / array_h)
        self.n_tiles   = ceil(N / array_w)
        self.num_tiles = self.m_tiles * self.n_tiles

        self.pol_factor  = 2 if "bipolar" in mul_type else 1
        self.mode_factor = 2 if "IS" in mul_type else 1

    # ---- per-tile energy (one H×W array pass, K-wide PEs, L cycles) ----
    # Counts use H,W for the array-mapped dims; K within the PE; L the stream.

    def weight_energy_per_tile(self):
        # Weights: K·W·L B-bit compares + RNG  (N-dim -> W for one tile)
        factor = self.pol_factor * self.mode_factor
        cmp = self.K * self.W * self.l * self.b * energy.__CMP * factor
        rng = self.K * self.W * self.l * self.b * energy.__RNG * factor
        return cmp + rng

    def input_energy_per_tile(self):
        # Inputs: H·K·L B-bit compares + RNG  (M-dim -> H for one tile)
        cmp = self.H * self.K * self.l * self.b * energy.__CMP
        rng = self.H * self.K * self.l * self.b * energy.__RNG
        return cmp + rng

    def pe_compute_energy_per_tile(self):
        # PE Comp: H·W·L  K-wide dot products
        if "unipolar" in self.mul_type:
            return self.H * self.W * self.l * energy.__AND
        else:  # bipolar
            return self.H * self.W * self.l * energy.__XNOR

    def output_energy_per_tile(self):
        # Outputs: H·W·L A-bit accumulates
        hwl   = self.H * self.W * self.l
        a_hwl = self.a * hwl
        # PC reduces (K+1) input wires per output
        kp1   = (self.K + 1) * self.W * self.l

        if self.acc_type == "uSADD":
            pc  = kp1 * energy.__PC
            add = kp1 * energy.__ACC
            return pc + add
        elif self.acc_type == "uNSADD":
            pc      = kp1 * energy.__PC
            acc_in  = a_hwl * energy.__ACC
            acc_off = a_hwl * energy.__ACC
            sub     = a_hwl * energy.__SUB
            cmp     = a_hwl * energy.__CMP
            return pc + acc_in + acc_off + sub + cmp
        else:
            raise ValueError(f"Unknown acc_type: {self.acc_type}")

    def energy_per_tile(self):
        return (self.weight_energy_per_tile()
                + self.input_energy_per_tile()
                + self.pe_compute_energy_per_tile()
                + self.output_energy_per_tile())

    # ---- cycles ----
    def get_cycles_per_tile(self):
        # "L latency" — one tile completes in L cycles
        return self.l

    def get_cycles(self):
        return self.num_tiles * self.get_cycles_per_tile()

    # ---- totals ----
    def get_energy(self):
        # energy methods already return total energy (L baked into counts).
        # Do NOT multiply by cycles — that would double-count L.
        return self.num_tiles * self.energy_per_tile()

    def summary(self):
        return {
            'num_tiles': self.num_tiles,
            'cycles':    self.get_cycles(),
            'energy':    self.get_energy(),
        }