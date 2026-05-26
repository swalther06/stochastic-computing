from math import ceil, log2
import os
import re
import subprocess

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UNIT_TO_W = {'mw': 1e-3, 'uw': 1e-6, 'nw': 1e-9, 'pw': 1e-12}


class Energy:
    """Component energy model parameterized by workload dimensions (M, N, K).

    Placeholder values scale linearly with circuit width until
    real numbers are loaded via synthesize().
    """

    def __init__(self, M: int, N: int, K: int,
                 precision: int = 8, clock: float = 1e-9):
        self.M = M
        self.N = N
        self.K = K
        self.precision = precision
        self.clock = clock

        b   = precision
        pcw = ceil(log2(K + 1))     # output width of a K-input popcount

        # ── Dynamic energy (J per operation) ──────────────────────────────────
        # 1-bit primitives
        self.NAND_DYN   = 1;  self.NOR_DYN    = 1;  self.XNOR_DYN   = 1
        self.AND_DYN    = 1;  self.NOT_DYN    = 1;  self.OR_DYN     = 1
        self.XOR_DYN    = 1;  self.MUX_DYN    = 1;  self.REG_DYN    = 1
        self.CMP_DYN    = 1;  self.FA_DYN     = 1;  self.SUB_DYN    = 1
        self.INC_DYN    = 1;  self.BSHIFT_DYN = 1;  self.ADD_DYN    = 1
        self.RNG_DYN    = 1.229e-13             # Nangate45 LFSR

        # size-dependent
        self.CTR_DYN    = b
        self.BSG_DYN    = self.RNG_DYN + self.CMP_DYN
        self.PC_DYN     = pcw
        self.ACC_DYN    = pcw
        self.MIN_DYN    = pcw

        self.SHIFT_DYN     = 1;  self.FIFO_DYN      = 1;  self.SEL_DYN       = 1
        self.HA_DYN        = 1;  self.BIN_CONV_DYN  = 1;  self.SKEW_CELL_DYN = 1
        self.RIM_INC_DYN   = b;  self.RIM_RD_DYN    = b;  self.SKEW_PC_DYN   = pcw
        self.MAC_BINARY_INT8_DYN = 1
        self.SRAM_READ_DYN = 1;  self.SRAM_WRITE_DYN = 1

        # ── Leakage power (W per instance) ────────────────────────────────────
        # 1-bit primitives
        self.NAND_LEAK  = 1;  self.NOR_LEAK   = 1;  self.XNOR_LEAK  = 1
        self.AND_LEAK   = 1;  self.NOT_LEAK   = 1;  self.OR_LEAK    = 1
        self.XOR_LEAK   = 1;  self.MUX_LEAK   = 1;  self.REG_LEAK   = 1
        self.CMP_LEAK   = 1;  self.FA_LEAK    = 1;  self.SUB_LEAK   = 1
        self.INC_LEAK   = 1;  self.BSHIFT_LEAK = 1; self.ADD_LEAK   = 1
        self.RNG_LEAK   = 2.28e-6               # Nangate45 LFSR

        # size-dependent
        self.CTR_LEAK   = b
        self.BSG_LEAK   = self.RNG_LEAK + self.CMP_LEAK
        self.PC_LEAK    = pcw
        self.ACC_LEAK   = pcw
        self.MIN_LEAK   = pcw

        self.SHIFT_LEAK    = 1;  self.FIFO_LEAK     = 1;  self.SEL_LEAK      = 1
        self.HA_LEAK       = 1;  self.BIN_CONV_LEAK = 1;  self.SKEW_CELL_LEAK = 1
        self.RIM_INC_LEAK  = b;  self.RIM_RD_LEAK   = b;  self.SKEW_PC_LEAK  = pcw
        self.MAC_BINARY_INT8_LEAK = 1
        self.SRAM_LEAK = 1      # per KB

    # ── Synthesis ──────────────────────────────────────────────────────────────

    def synthesize(self, syn_dir: str = None) -> None:
        """Generate parameterized wrappers, run DC synthesis, update energies from reports."""
        if syn_dir is None:
            syn_dir = os.path.join(_REPO_ROOT, 'synthesis')
        rtl_dir     = os.path.join(syn_dir, 'verilog')
        reports_dir = os.path.join(syn_dir, 'reports')

        b   = self.precision
        K   = self.K
        N   = max(2, self.N)
        pcw = ceil(log2(K + 1))

        # (top_module_name, sv_source, dyn_attr, leak_attr)
        targets = [
            (f'pc_K{K}',       self._sv_pc(K, pcw),      'PC_DYN',      'PC_LEAK'),
            (f'acc_W{pcw}',    self._sv_acc(pcw),         'ACC_DYN',     'ACC_LEAK'),
            (f'ctr_W{b}',      self._sv_ctr(b),           'CTR_DYN',     'CTR_LEAK'),
            ('rng_N8',         self._sv_rng(),             'RNG_DYN',     'RNG_LEAK'),
            ('bsg_N8',         self._sv_bsg(),             'BSG_DYN',     'BSG_LEAK'),
            (f'min_W{pcw}',    self._sv_min(pcw),         'MIN_DYN',     'MIN_LEAK'),
            (f'shift_D{N}',    self._sv_shift(N),         'SHIFT_DYN',   'SHIFT_LEAK'),
            (f'fifo_D{N}',     self._sv_fifo(N),          'FIFO_DYN',    'FIFO_LEAK'),
            (f'rim_inc_W{b}',  self._sv_rim_inc(b),       'RIM_INC_DYN', 'RIM_INC_LEAK'),
            (f'rim_rd_W{b}',   self._sv_rim_rd(b),        'RIM_RD_DYN',  'RIM_RD_LEAK'),
            (f'bin_conv_A{b}', self._sv_bin_conv(b),      'BIN_CONV_DYN','BIN_CONV_LEAK'),
            (f'skew_pc_K{K}',  self._sv_skew_pc(K, pcw), 'SKEW_PC_DYN', 'SKEW_PC_LEAK'),
        ]

        os.makedirs(reports_dir, exist_ok=True)

        for top, sv, dyn_attr, leak_attr in targets:
            sv_path  = os.path.join(rtl_dir,     f'{top}.sv')
            log_path = os.path.join(reports_dir, f'{top}_synth.log')
            rpt_path = os.path.join(reports_dir, f'{top}_power.rpt')

            print(f'[Energy.synthesize] {top} ...', flush=True)
            with open(sv_path, 'w') as fh:
                fh.write(sv)
            try:
                result = subprocess.run(
                    ['make', top],
                    cwd=_REPO_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                with open(log_path, 'w') as fh:
                    fh.write(result.stdout or '')

                if os.path.exists(rpt_path):
                    dyn, leak = _parse_power_report(rpt_path)
                    if dyn  is not None: setattr(self, dyn_attr,  dyn * self.clock)
                    if leak is not None: setattr(self, leak_attr, leak)
                    print(f'[Energy.synthesize] {top} OK')
                else:
                    print(f'[Energy.synthesize] WARNING: {top} — no power report generated '
                          f'(dc_shell may have failed; see {log_path})')
            finally:
                if os.path.exists(sv_path):
                    os.remove(sv_path)

    # ── Wrapper generators ─────────────────────────────────────────────────────

    def _sv_pc(self, K, pcw):
        return (f"module pc_K{K} (\n"
                f"    input  [{K-1}:0]   bits,\n"
                f"    output [{pcw-1}:0] count\n"
                f");\n"
                f"    assign count = $countones(bits);\n"
                f"endmodule\n")

    def _sv_acc(self, W):
        return (f"module acc_W{W} (\n"
                f"    input              clk, rst,\n"
                f"    input  [{W-1}:0]   in,\n"
                f"    output reg [{W-1}:0] sum\n"
                f");\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) sum <= 0;\n"
                f"        else     sum <= sum + in;\n"
                f"    end\n"
                f"endmodule\n")

    def _sv_ctr(self, W):
        return (f"module ctr_W{W} (\n"
                f"    input              clk, rst,\n"
                f"    output reg [{W-1}:0] count\n"
                f");\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) count <= 0;\n"
                f"        else     count <= count + 1;\n"
                f"    end\n"
                f"endmodule\n")

    def _sv_rng(self):
        return ("module rng_N8 (\n"
                "    input              clk, rst,\n"
                "    output reg [7:0]   rnd_out\n"
                ");\n"
                "    wire feedback = rnd_out[7] ^ rnd_out[5] ^ rnd_out[4] ^ rnd_out[3];\n"
                "    always_ff @(posedge clk or posedge rst) begin\n"
                "        if (rst) rnd_out <= 8'hFF;\n"
                "        else     rnd_out <= {rnd_out[6:0], feedback};\n"
                "    end\n"
                "endmodule\n")

    def _sv_bsg(self):
        return ("module bsg_N8 (\n"
                "    input          clk, rst,\n"
                "    input  [7:0]   val,\n"
                "    output         bs_out\n"
                ");\n"
                "    reg [7:0] lfsr;\n"
                "    wire feedback = lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3];\n"
                "    always_ff @(posedge clk or posedge rst) begin\n"
                "        if (rst) lfsr <= 8'hFF;\n"
                "        else     lfsr <= {lfsr[6:0], feedback};\n"
                "    end\n"
                "    assign bs_out = (lfsr < val);\n"
                "endmodule\n")

    def _sv_min(self, W):
        return (f"module min_W{W} (\n"
                f"    input  [{W-1}:0] a, b,\n"
                f"    output [{W-1}:0] y\n"
                f");\n"
                f"    assign y = (a < b) ? a : b;\n"
                f"endmodule\n")

    def _sv_shift(self, D):
        D = max(2, D)
        return (f"module shift_D{D} (\n"
                f"    input  clk, rst, d,\n"
                f"    output q\n"
                f");\n"
                f"    reg [{D-1}:0] sr;\n"
                f"    assign q = sr[{D-1}];\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) sr <= 0;\n"
                f"        else     sr <= {{sr[{D-2}:0], d}};\n"
                f"    end\n"
                f"endmodule\n")

    def _sv_fifo(self, D):
        D  = max(2, D)
        aw = max(1, ceil(log2(D)))
        cw = aw + 1
        return (f"module fifo_D{D} (\n"
                f"    input          clk, rst, wr_en, rd_en, din,\n"
                f"    output reg     dout,\n"
                f"    output         full, empty\n"
                f");\n"
                f"    reg [{D-1}:0]  mem;\n"
                f"    reg [{cw-1}:0] count;\n"
                f"    reg [{aw-1}:0] wr_ptr, rd_ptr;\n"
                f"    assign full  = (count == {D});\n"
                f"    assign empty = (count == 0);\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) begin wr_ptr <= 0; rd_ptr <= 0; count <= 0; dout <= 0; end\n"
                f"        else begin\n"
                f"            if (wr_en && !full)  begin mem[wr_ptr] <= din;      wr_ptr <= wr_ptr + 1; count <= count + 1; end\n"
                f"            if (rd_en && !empty) begin dout <= mem[rd_ptr]; rd_ptr <= rd_ptr + 1; count <= count - 1; end\n"
                f"        end\n"
                f"    end\n"
                f"endmodule\n")

    def _sv_rim_inc(self, W):
        return (f"module rim_inc_W{W} (\n"
                f"    input              clk, rst, inc,\n"
                f"    output reg [{W-1}:0] val\n"
                f");\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) val <= 0;\n"
                f"        else if (inc) val <= val + 1;\n"
                f"    end\n"
                f"endmodule\n")

    def _sv_rim_rd(self, W):
        return (f"module rim_rd_W{W} (\n"
                f"    input  [{W-1}:0] val,\n"
                f"    input            rd_en,\n"
                f"    output [{W-1}:0] out\n"
                f");\n"
                f"    assign out = rd_en ? val : {{{W}{{1'b0}}}};\n"
                f"endmodule\n")

    def _sv_bin_conv(self, A):
        return (f"module bin_conv_A{A} (\n"
                f"    input              clk, rst, skew_in,\n"
                f"    output reg [{A-1}:0] bin_out\n"
                f");\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) bin_out <= 0;\n"
                f"        else if (skew_in) bin_out <= bin_out + 1;\n"
                f"    end\n"
                f"endmodule\n")

    def _sv_skew_pc(self, K, A):
        return (f"module skew_pc_K{K} (\n"
                f"    input              clk, rst,\n"
                f"    input  [{K-1}:0]   bits,\n"
                f"    output reg [{A-1}:0] count\n"
                f");\n"
                f"    always_ff @(posedge clk or posedge rst) begin\n"
                f"        if (rst) count <= 0;\n"
                f"        else     count <= count + $countones(bits);\n"
                f"    end\n"
                f"endmodule\n")


def _parse_power_report(path: str):
    """Parse a Synopsys DC report_power file.

    Returns (dynamic_W, leakage_W) — or (None, None) if the expected line is absent.
    The Total line format: internal <unit>  switching <unit>  leakage <unit>  total <unit>
    """
    with open(path) as fh:
        text = fh.read()

    m = re.search(
        r'Total\s+'
        r'([\d.e+\-]+)\s+(mW|uW|nW|pW)\s+'
        r'([\d.e+\-]+)\s+(mW|uW|nW|pW)\s+'
        r'([\d.e+\-]+)\s+(mW|uW|nW|pW)',
        text, re.IGNORECASE,
    )
    if not m:
        return None, None

    internal  = float(m.group(1)) * _UNIT_TO_W[m.group(2).lower()]
    switching = float(m.group(3)) * _UNIT_TO_W[m.group(4).lower()]
    leakage   = float(m.group(5)) * _UNIT_TO_W[m.group(6).lower()]
    return internal + switching, leakage
