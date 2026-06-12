from math import ceil, log2
import json
import os
import re
import subprocess
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UNIT_TO_W = {'mw': 1e-3, 'uw': 1e-6, 'nw': 1e-9, 'pw': 1e-12}

# Location of the compiled CACTI 7 binary. Adjust if yours lives elsewhere.
_CACTI_DIR = os.path.join(_REPO_ROOT, 'analytical_modeling', 'cacti7')
_CACTI_BIN = os.path.join(_CACTI_DIR, 'cacti')

# CACTI cannot model an access (block) width narrower than 64 bytes.
_CACTI_MIN_BLOCK_BYTES = 64

# Attributes whose value scales with K (uGEMM-specific); everything else is
# determined solely by precision + array dimensions + SRAM sizes.
_UGEMM_ATTRS = frozenset({
    'PC_DYN',     'PC_LEAK',
    'ACC_DYN',    'ACC_LEAK',
    'MIN_DYN',    'MIN_LEAK',
    'SKEW_PC_DYN','SKEW_PC_LEAK',
    'RIM_INC_DYN','RIM_INC_LEAK',
})


class Energy:
    """Component energy model parameterized by workload (M, N, K) and the
    physical array dimensions (array_h, array_w).

    Compute-component energies come from Synopsys DC synthesis (synthesize()).
    SRAM energies come from CACTI (run_cacti()).

    SRAM access WIDTHS (bytes per access) are derived from the array edge each
    operand is fed/drained along (typical WS mapping):
        ifmap  -> array_h elements per access   (A streams in along rows)
        filter -> array_w elements per access   (B loads along columns)
        ofmap  -> array_w elements per access   (C drains along columns)
    These set CACTI's block size (floored at 64 B). The matching access COUNTS
    live in the architecture models / dataflow helper, and must be counted in
    these same access-width units.

    Conventions:
      *_DYN     : dynamic ENERGY per operation/access (J).
      *_LEAK    : leakage POWER (W).
      *_LEAK_W  : absolute leakage POWER of one SRAM (W), from CACTI.
    """

    def __init__(self, M: int, N: int, K: int,
                 array_h: int = 64, array_w: int = 64,
                 precision: int = 8, freq: float = 1e9,
                 ifmap_sram_kB: float = 1024,
                 filter_sram_kB: float = 1024,
                 ofmap_sram_kB: float = 1024,
                 run_cacti: bool = False):
        """Set placeholder energies, load the cache, then apply hardcoded literature values."""
        self.M = M
        self.N = N
        self.K = K
        self.array_h = array_h
        self.array_w = array_w
        self.precision = precision
        self.freq  = freq
        self.clock = 1.0 / freq

        self.ifmap_sram_kB  = ifmap_sram_kB
        self.filter_sram_kB = filter_sram_kB
        self.ofmap_sram_kB  = ofmap_sram_kB

        eb = max(1, precision // 8)   # element bytes
        # Per-SRAM access widths from array edges, floored at CACTI's 64 B.
        self.ifmap_access_bytes  = max(_CACTI_MIN_BLOCK_BYTES, array_h * eb)
        self.filter_access_bytes = max(_CACTI_MIN_BLOCK_BYTES, array_w * eb)
        self.ofmap_access_bytes  = max(_CACTI_MIN_BLOCK_BYTES, array_w * eb)

        b   = precision
        pcw = ceil(log2(K + 1))     # output width of a K-input popcount

        # -- Dynamic energy (J per operation) ---------------------------------
        _G_DYN  = 1e-14     # J -- 1-bit gate, Nangate45 45nm estimate

        self.NAND_DYN   = _G_DYN;  self.NOR_DYN    = _G_DYN;  self.XNOR_DYN   = _G_DYN
        self.AND_DYN    = _G_DYN;  self.NOT_DYN    = _G_DYN;  self.OR_DYN     = _G_DYN
        self.XOR_DYN    = _G_DYN;  self.MUX_DYN    = _G_DYN;  self.REG_DYN    = _G_DYN
        self.CMP_DYN    = _G_DYN;  self.FA_DYN     = _G_DYN;  self.SUB_DYN    = _G_DYN
        self.INC_DYN    = _G_DYN;  self.BSHIFT_DYN = _G_DYN;  self.ADD_DYN    = _G_DYN
        
        self.RNG_DYN             = 1.229e-13
        self.CTR_DYN             = b   * _G_DYN
        self.BSG_DYN             = self.RNG_DYN + self.CMP_DYN
        self.PC_DYN              = pcw * _G_DYN
        self.ACC_DYN             = pcw * _G_DYN
        self.MIN_DYN             = pcw * _G_DYN
        self.SHIFT_DYN           = _G_DYN
        self.FIFO_DYN            = _G_DYN
        self.SEL_DYN             = _G_DYN
        self.HA_DYN              = _G_DYN
        self.BIN_CONV_DYN        = _G_DYN
        self.SKEW_CELL_DYN       = _G_DYN
        self.RIM_INC_DYN         = b   * _G_DYN
        self.RIM_RD_DYN          = b   * _G_DYN
        self.SKEW_PC_DYN         = pcw * _G_DYN
       

        # -- Leakage power (W per instance) -----------------------------------
        _G_LEAK = 1e-6   # W -- 1-bit gate, Nangate45 45nm estimate

        self.NAND_LEAK  = _G_LEAK;  self.NOR_LEAK   = _G_LEAK;  self.XNOR_LEAK  = _G_LEAK
        self.AND_LEAK   = _G_LEAK;  self.NOT_LEAK   = _G_LEAK;  self.OR_LEAK    = _G_LEAK
        self.XOR_LEAK   = _G_LEAK;  self.MUX_LEAK   = _G_LEAK;  self.REG_LEAK   = _G_LEAK
        self.CMP_LEAK   = _G_LEAK;  self.FA_LEAK    = _G_LEAK;  self.SUB_LEAK   = _G_LEAK
        self.INC_LEAK   = _G_LEAK;  self.BSHIFT_LEAK = _G_LEAK; self.ADD_LEAK   = _G_LEAK
        
        self.RNG_LEAK             = 2.28e-6
        self.CTR_LEAK             = b   * _G_LEAK
        self.BSG_LEAK             = self.RNG_LEAK + self.CMP_LEAK
        self.PC_LEAK              = pcw * _G_LEAK
        self.ACC_LEAK             = pcw * _G_LEAK
        self.MIN_LEAK             = pcw * _G_LEAK
        self.SHIFT_LEAK           = _G_LEAK
        self.FIFO_LEAK            = _G_LEAK
        self.SEL_LEAK             = _G_LEAK
        self.HA_LEAK              = _G_LEAK
        self.BIN_CONV_LEAK        = _G_LEAK
        self.SKEW_CELL_LEAK       = _G_LEAK
        self.RIM_INC_LEAK         = b   * _G_LEAK
        self.RIM_RD_LEAK          = b   * _G_LEAK
        self.SKEW_PC_LEAK         = pcw * _G_LEAK

        # -- SRAM energy/leakage (per-SRAM, populated by CACTI) ---------------
        _sram_rd_ph = b * _G_DYN
        _sram_wr_ph = b * _G_DYN
        self.IFMAP_SRAM_READ_DYN   = _sram_rd_ph
        self.IFMAP_SRAM_WRITE_DYN  = _sram_wr_ph
        self.FILTER_SRAM_READ_DYN  = _sram_rd_ph
        self.FILTER_SRAM_WRITE_DYN = _sram_wr_ph
        self.OFMAP_SRAM_READ_DYN   = _sram_rd_ph
        self.OFMAP_SRAM_WRITE_DYN  = _sram_wr_ph
        self.IFMAP_SRAM_LEAK_W     = ifmap_sram_kB  * _G_LEAK
        self.FILTER_SRAM_LEAK_W    = filter_sram_kB * _G_LEAK
        self.OFMAP_SRAM_LEAK_W     = ofmap_sram_kB  * _G_LEAK

        self._load_cache()
        if run_cacti:
            self._cacti_populate()

        self.RNG_DYN             = 1.229e-13
        #self.MAC_BINARY_INT8_DYN = 0.434e-12
        #self.MAC_UNARY_INT8_DYN  = 0.337e-12
        self.RNG_LEAK             = 2.28e-6
        #self.MAC_BINARY_INT8_LEAK = 25.36e-6
        self.PE_BINARY_INT8_DYN       = 0.258e-12
        self.PE_BINARY_INT8_LEAK      = 47.91e-6
        self.PE_USYS_INT8_DYN        = 0.199e-12
        self.PE_USYS_INT8_LEAK       = 16.22e-6

        self._recompute_derived()
        self._save_cache()



    # -- CACTI (SRAM energy) --------------------------------------------------

    def run_cacti(self, syn_dir: str = None) -> None:
        """Run CACTI for each SRAM buffer and save results to the cache."""
        self._cacti_populate()
        self._save_cache(syn_dir)

    def _cacti_populate(self) -> None:
        """Run CACTI for each SRAM buffer and update SRAM energy/leakage attrs in place."""
        if not os.path.exists(_CACTI_BIN):
            print(f'[Energy] CACTI binary not found at {_CACTI_BIN}; '
                  f'run `make` in {_CACTI_DIR}. Keeping placeholder SRAM values.')
            return

        sram_specs = [
            ('IFMAP',  self.ifmap_sram_kB,  self.ifmap_access_bytes),
            ('FILTER', self.filter_sram_kB, self.filter_access_bytes),
            ('OFMAP',  self.ofmap_sram_kB,  self.ofmap_access_bytes),
        ]
        results_by_cfg: dict = {}

        for label, kB, access_bytes in sram_specs:
            cfg_key = (kB, access_bytes)
            if cfg_key not in results_by_cfg:
                results_by_cfg[cfg_key] = self._run_cacti(kB, access_bytes)
            rd_J, wr_J, leak_W = results_by_cfg[cfg_key]
            if rd_J is None:
                print(f'[Energy] CACTI parse failed for {label} '
                      f'({kB} kB, {access_bytes} B/access); keeping placeholders.')
                continue
            setattr(self, f'{label}_SRAM_READ_DYN',  rd_J)
            setattr(self, f'{label}_SRAM_WRITE_DYN', wr_J)
            setattr(self, f'{label}_SRAM_LEAK_W',    leak_W)
            print(f'[Energy] CACTI {label} {kB} kB, {access_bytes} B/access: '
                  f'rd={rd_J*1e12:.2f} pJ, wr={wr_J*1e12:.2f} pJ, '
                  f'leak={leak_W*1e3:.2f} mW')

    def _run_cacti(self, sram_kB: float, access_bytes: int):
        """Write a temp CACTI config, invoke the binary, return (read_J, write_J, leak_W) or (None,)*3."""
        cfg = self._cacti_cfg(sram_kB, access_bytes)
        with tempfile.NamedTemporaryFile('w', suffix='.cfg', delete=False) as fh:
            fh.write(cfg)
            cfg_path = fh.name
        try:
            result = subprocess.run(
                [_CACTI_BIN, '-infile', cfg_path],
                cwd=_CACTI_DIR,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            out = result.stdout or ''
        except OSError as e:
            print(f'[Energy._run_cacti] could not run CACTI: {e}')
            return None, None, None
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

        rd_J, wr_J, leak_W = _parse_cacti_output(out)
        if rd_J is None:
            print(f'[Energy._run_cacti] parse failed for {sram_kB} kB / '
                  f'{access_bytes} B. First 800 chars of CACTI output:\n{out[:800]}')
        return rd_J, wr_J, leak_W

    def _cacti_cfg(self, sram_kB: float, access_bytes: int) -> str:
        """CACTI 7 scratchpad (RAM mode) config matching shipped cache.cfg syntax.
        block size = access_bytes (per-access width; CACTI floors at 64 B)."""
        size_bytes  = int(sram_kB * 1024)
        block_bytes = max(_CACTI_MIN_BLOCK_BYTES, int(access_bytes))
        bus_bits    = block_bytes * 8
        tech_u      = 0.045
        return f"""# Auto-generated scratchpad SRAM config (matches cache.cfg syntax)
-size (bytes) {size_bytes}

-Array Power Gating - "false"
-WL Power Gating - "false"
-CL Power Gating - "false"
-Bitline floating - "false"
-Interconnect Power Gating - "false"
-Power Gating Performance Loss 0.01

-block size (bytes) {block_bytes}

-associativity 1

-read-write port 1
-exclusive read port 0
-exclusive write port 0
-single ended read ports 0

-UCA bank count 1
-technology (u) {tech_u}

-page size (bits) 8192
-burst length 8
-internal prefetch width 8

-Data array cell type - "itrs-hp"
-Data array peripheral type - "itrs-hp"
-Tag array cell type - "itrs-hp"
-Tag array peripheral type - "itrs-hp"

-output/input bus width {bus_bits}

-operating temperature (K) 360

-cache type "ram"

-tag size (b) "default"

-access mode (normal, sequential, fast) - "normal"

-design objective (weight delay, dynamic power, leakage power, cycle time, area) 0:0:0:100:0
-deviate (delay, dynamic power, leakage power, cycle time, area) 20:100000:100000:100000:100000

-NUCAdesign objective (weight delay, dynamic power, leakage power, cycle time, area) 100:100:0:0:100
-NUCAdeviate (delay, dynamic power, leakage power, cycle time, area) 10:10000:10000:10000:10000

-Optimize ED or ED^2 (ED, ED^2, NONE): "ED^2"

-Cache model (NUCA, UCA)  - "UCA"

-NUCA bank count 0

-Wire signaling (fullswing, lowswing, default) - "Global_30"

-Wire inside mat - "semi-global"
-Wire outside mat - "semi-global"

-Interconnect projection - "conservative"

-Core count 8
-Cache level (L2/L3) - "L3"

-Add ECC - "true"

-Print level (DETAILED, CONCISE) - "DETAILED"

-Print input parameters - "false"

-Force cache config - "false"
-Ndwl 1
-Ndbl 1
-Nspd 0
-Ndcm 1
-Ndsam1 0
-Ndsam2 0

-dram_type "D"
-iostate "W"
-dram_ecc "Y"
-addr_timing 1.0
-bus_bw  12.8 GBps
-mem_density 4 Gb
-bus_freq 800 MHz
-duty_cycle 1.0
-activity_dq 1.0
-activity_ca 0.5
-num_dq 72
-num_dqs 18
-num_ca 25
-num_clk  2
-num_mem_dq 2
-mem_data_width 8
""".strip()

    # -- Synthesis ------------------------------------------------------------

    def synthesize(self, syn_dir: str = None, include_ugemm: bool = True,
                   ugemm_only: bool = False) -> None:
        """Run DC synthesis for all RTL targets, update compute-component energies, and save cache.

        include_ugemm=False  -- skip uGEMM targets (pc/acc/min); reuse across workloads.
        ugemm_only=True      -- synthesize only uGEMM targets (K-dependent); caller is
                                responsible for copying general attrs from a prior synthesis.
        """
        if syn_dir is None:
            syn_dir = os.path.join(_REPO_ROOT, 'synthesis')
        rtl_dir     = os.path.join(syn_dir, 'verilog')
        reports_dir = os.path.join(syn_dir, 'reports')

        targets = self._synthesis_targets(include_ugemm=include_ugemm, ugemm_only=ugemm_only)
        os.makedirs(reports_dir, exist_ok=True)

        for top, src_file, src_mod, params, port_decl, port_conn, dyn_attr, leak_attr in targets:
            src_path = os.path.join(rtl_dir, src_file)
            if not os.path.exists(src_path):
                print(f'[Energy.synthesize] SKIP: {top} -- {src_file} not found')
                continue
            with open(src_path) as fh:
                src = fh.read()
            if src_mod is None:
                sv = src
            else:
                param_str = ', '.join(f'.{k}({v})' for k, v in params.items())
                sv = (src +
                      f'\nmodule {top} ({port_decl});\n'
                      f'    {src_mod} #({param_str}) u ({port_conn});\n'
                      f'endmodule\n')
            sv_path   = os.path.join(rtl_dir,     f'{top}.sv')
            log_path  = os.path.join(reports_dir, f'{top}_synth.log')
            rpt_path  = os.path.join(reports_dir, f'{top}_power.rpt')
            time_path = os.path.join(reports_dir, f'{top}_timing.rpt')
            print(f'[Energy.synthesize] {top} ...', flush=True)
            with open(sv_path, 'w') as fh:
                fh.write(sv)
            try:
                result = subprocess.run(
                    ['make', top], cwd=_REPO_ROOT, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                with open(log_path, 'w') as fh:
                    fh.write(result.stdout or '')
                if not self._apply_report(top, rpt_path, time_path, dyn_attr, leak_attr):
                    print(f'[Energy.synthesize] WARNING: {top} -- no power report '
                          f'(see {log_path})')
            finally:
                if os.path.exists(sv_path):
                    os.remove(sv_path)

        self._recompute_derived()
        self._save_cache(syn_dir)

    def _synthesis_targets(self, include_ugemm: bool = True, ugemm_only: bool = False):
        """Return list of (top, src_file, src_mod, params, port_decl, port_conn, dyn_attr, leak_attr) tuples."""
        b    = self.precision
        K    = self.K
        N    = max(2, self.N)
        pcw  = ceil(log2(K + 1))
        pcw1 = ceil(log2(K + 2))
        ugemm_targets = [
            (f'pc_K{K+1}', 'ugemm.sv', 'pc', {'K': K+1},
             f'input [{K}:0] bits, output [{pcw1-1}:0] count',
             '.bits(bits), .count(count)', 'PC_DYN', 'PC_LEAK'),
            (f'acc_W{pcw}', 'ugemm.sv', 'acc', {'W': pcw},
             f'input clk, rst, input [{pcw-1}:0] in, output [{pcw-1}:0] sum',
             '.clk(clk), .rst(rst), .in(in), .sum(sum)', 'ACC_DYN', 'ACC_LEAK'),
            (f'min_W{pcw}', 'ugemm.sv', 'min_unit', {'W': pcw},
             f'input [{pcw-1}:0] a, b, output [{pcw-1}:0] y',
             '.a(a), .b(b), .y(y)', 'MIN_DYN', 'MIN_LEAK'),
        ]
        general_targets = [
            (f'ctr_W{b}', 'basic_comp.sv', 'ctr', {'W': b},
             f'input clk, rst, output [{b-1}:0] count',
             '.clk(clk), .rst(rst), .count(count)', 'CTR_DYN', 'CTR_LEAK'),
            #(f'shift_D{N}_W{b}', 'systolic.sv', 'shift_reg', {'DEPTH': N, 'W': b},
            # f'input clk, rst, input [{b-1}:0] d, output [{b-1}:0] q',
            # '.clk(clk), .rst(rst), .d(d), .q(q)', 'SHIFT_DYN', 'SHIFT_LEAK'),
            #(f'fifo_D{N}_W{b}', 'systolic.sv', 'sc_fifo', {'DEPTH': N, 'W': b},
            # f'input clk, rst, wr_en, rd_en, input [{b-1}:0] din, output [{b-1}:0] dout, output full, empty',
            # '.clk(clk), .rst(rst), .wr_en(wr_en), .rd_en(rd_en), .din(din)'
            # ', .dout(dout), .full(full), .empty(empty)', 'FIFO_DYN', 'FIFO_LEAK'),
            (f'bin_conv_A{b}', 'cambricon.sv', 'bin_conv', {'A': b},
             f'input clk, rst, skew_in, output [{b-1}:0] bin_out',
             '.clk(clk), .rst(rst), .skew_in(skew_in), .bin_out(bin_out)',
             'BIN_CONV_DYN', 'BIN_CONV_LEAK'),
            ('nand_gate', 'logic_gates.sv', None, {}, None, None, 'NAND_DYN',  'NAND_LEAK'),
            ('nor_gate',  'logic_gates.sv', None, {}, None, None, 'NOR_DYN',   'NOR_LEAK'),
            ('xnor_gate', 'logic_gates.sv', None, {}, None, None, 'XNOR_DYN',  'XNOR_LEAK'),
            ('and_gate',  'logic_gates.sv', None, {}, None, None, 'AND_DYN',   'AND_LEAK'),
            ('or_gate',   'logic_gates.sv', None, {}, None, None, 'OR_DYN',    'OR_LEAK'),
            ('xor_gate',  'logic_gates.sv', None, {}, None, None, 'XOR_DYN',   'XOR_LEAK'),
            ('not_gate',  'logic_gates.sv', None, {}, None, None, 'NOT_DYN',   'NOT_LEAK'),
            (f'mux_W{b}', 'basic_comp.sv', 'mux', {'W': b},
             f'input sel, input [{b-1}:0] a, input [{b-1}:0] b, output [{b-1}:0] y',
             '.sel(sel), .a(a), .b(b), .y(y)', 'MUX_DYN', 'MUX_LEAK'),
            (f'dff_W{1}', 'basic_comp.sv', 'dff', {'W': 1},
             f'input clk, rst, input [0:0] d, output [0:0] q',
             '.clk(clk), .rst(rst), .d(d), .q(q)', 'REG_DYN', 'REG_LEAK'),
            (f'cmp_W{b}', 'basic_comp.sv', 'cmp', {'W': b},
             f'input [{b-1}:0] a, b, output lt',
             '.a(a), .b(b), .lt(lt)', 'CMP_DYN', 'CMP_LEAK'),
            #('fa',   'basic_comp.sv', None, {}, None, None, 'FA_DYN',  'FA_LEAK'),
            (f'add_W{b}', 'basic_comp.sv', 'add', {'W': b},
             f'input [{b-1}:0] a, b, output [{b-1}:0] sum',
             '.a(a), .b(b), .sum(sum)', 'ADD_DYN', 'ADD_LEAK'),
            (f'inc_W{b}', 'basic_comp.sv', 'inc', {'W': b},
             f'input [{b-1}:0] a, output [{b-1}:0] b',
             '.a(a), .b(b)', 'INC_DYN', 'INC_LEAK'),
            (f'bshift_W{b}', 'basic_comp.sv', 'bshift', {'WIDTH': b},
             f'input clk, rst, input [{b-1}:0] in, output [{b-1}:0] out',
             '.clk(clk), .rst(rst), .in(in), .out(out)', 'BSHIFT_DYN', 'BSHIFT_LEAK'),
            ('ha',              'cambricon.sv', None, {}, None, None, 'HA_DYN',              'HA_LEAK'),
            ('sel_unit',        'systolic.sv',  None, {}, None, None, 'SEL_DYN',             'SEL_LEAK'),
            #('mac_binary_int8', 'binary.sv',    None, {}, None, None, 'MAC_BINARY_INT8_DYN', 'MAC_BINARY_INT8_LEAK'),
        ]
        if ugemm_only:
            return ugemm_targets
        return (ugemm_targets if include_ugemm else []) + general_targets

    def _apply_report(self, top, rpt_path, time_path, dyn_attr, leak_attr):
        """Parse a power/timing report pair and write results to dyn_attr/leak_attr. Returns True on success."""
        if not os.path.exists(rpt_path):
            return False
        dyn_W, leak_W = _parse_power_report(rpt_path)
        slack_met     = _parse_timing_slack(time_path) if os.path.exists(time_path) else None
        if leak_W is not None:
            setattr(self, leak_attr, leak_W)
        if dyn_W is not None:
            if slack_met is False:
                print(f'[Energy] WARNING: {top} -- timing VIOLATED, skipping dynamic energy update')
            else:
                setattr(self, dyn_attr, dyn_W * self.clock)
        status = ('timing MET' if slack_met is True else
                  'timing VIOLATED' if slack_met is False else 'timing unknown')
        print(f'[Energy] {top} OK ({status})')
        return True

    def reload_from_reports(self, syn_dir: str = None, include_ugemm: bool = True) -> None:
        """Re-parse existing synthesis reports and refresh the cache without re-running DC."""
        if syn_dir is None:
            syn_dir = os.path.join(_REPO_ROOT, 'synthesis')
        reports_dir = os.path.join(syn_dir, 'reports')
        updated = 0
        for top, *_, dyn_attr, leak_attr in self._synthesis_targets(include_ugemm=include_ugemm):
            rpt_path  = os.path.join(reports_dir, f'{top}_power.rpt')
            time_path = os.path.join(reports_dir, f'{top}_timing.rpt')
            if self._apply_report(top, rpt_path, time_path, dyn_attr, leak_attr):
                updated += 1
            else:
                print(f'[Energy.reload_from_reports] SKIP: {top} -- no report')
        print(f'[Energy.reload_from_reports] updated {updated} targets')
        self._recompute_derived()
        self._save_cache(syn_dir)

    def _recompute_derived(self) -> None:
        """Recompute energy values derived from synthesized primitives."""
        self.RIM_INC_DYN  = self.INC_DYN  / 2.0
        self.RIM_INC_LEAK = self.INC_LEAK / 2.0
        self.RIM_ADD_DYN  = self.ADD_DYN
        self.RIM_ADD_LEAK = self.ADD_LEAK

    # -- Cache ----------------------------------------------------------------

    def _base_cache_key(self) -> str:
        """Key for non-uGEMM values (precision + array dims + SRAM sizes only)."""
        return (f'{self.precision}b_A{self.array_h}x{self.array_w}'
                f'_I{int(self.ifmap_sram_kB)}'
                f'_F{int(self.filter_sram_kB)}'
                f'_O{int(self.ofmap_sram_kB)}')

    def _cache_key(self) -> str:
        """Full key encoding all parameters, including K/N for uGEMM-specific values."""
        return (f'{self.precision}b_K{self.K}_N{self.N}_A{self.array_h}x{self.array_w}'
                f'_I{int(self.ifmap_sram_kB)}'
                f'_F{int(self.filter_sram_kB)}'
                f'_O{int(self.ofmap_sram_kB)}')

    def _cache_path(self, syn_dir: str = None) -> str:
        """Return absolute path to energy_cache.json."""
        if syn_dir is None:
            syn_dir = os.path.join(_REPO_ROOT, 'synthesis')
        return os.path.join(syn_dir, 'energy_cache.json')

    def _load_cache(self, syn_dir: str = None) -> None:
        """Load cached energy values into instance attrs.

        Base (non-uGEMM) values are loaded first from the base key; uGEMM-specific
        values are then overlaid from the full key if it exists.
        """
        path = self._cache_path(syn_dir)
        if not os.path.exists(path):
            return
        try:
            with open(path) as fh:
                cache = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return
        for attr, val in cache.get(self._base_cache_key(), {}).items():
            if hasattr(self, attr):
                setattr(self, attr, val)
        for attr, val in cache.get(self._cache_key(), {}).items():
            if hasattr(self, attr):
                setattr(self, attr, val)

    def _save_cache(self, syn_dir: str = None) -> None:
        """Write energy attrs into energy_cache.json.

        Non-uGEMM attrs are stored under the base key (precision + dims + SRAM);
        all attrs are also stored under the full key (includes K/N).  This lets a
        new MNK configuration seed its non-uGEMM values from the base key without
        re-running synthesis.
        """
        path = self._cache_path(syn_dir)
        cache: dict = {}
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    cache = json.load(fh)
            except (json.JSONDecodeError, OSError):
                cache = {}
        all_energy = {
            attr: val for attr, val in vars(self).items()
            if attr.endswith('_DYN') or attr.endswith('_LEAK') or attr.endswith('_LEAK_W')
        }
        cache[self._base_cache_key()] = {
            attr: val for attr, val in all_energy.items()
            if attr not in _UGEMM_ATTRS
        }
        cache[self._cache_key()] = all_energy
        with open(path, 'w') as fh:
            json.dump(cache, fh, indent=2)


def _parse_power_report(path: str):
    """Parse a Synopsys DC report_power -hier file; return (dynamic_W, leakage_W) or (None, None)."""
    with open(path) as fh:
        text = fh.read()
    dyn_m  = re.search(r'Dynamic Power Units\s*=\s*1\s*(\w+)', text, re.IGNORECASE)
    leak_m = re.search(r'Leakage Power Units\s*=\s*1\s*(\w+)', text, re.IGNORECASE)
    dyn_scale  = _UNIT_TO_W.get((dyn_m.group(1)  if dyn_m  else 'mW').lower(), 1e-3)
    leak_scale = _UNIT_TO_W.get((leak_m.group(1) if leak_m else 'nW').lower(), 1e-9)
    m = re.search(
        r'^\S.*?\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+[\d.e+\-]+\s+100\.',
        text, re.MULTILINE,
    )
    if not m:
        return None, None
    switch_W = float(m.group(1)) * dyn_scale
    int_W    = float(m.group(2)) * dyn_scale
    leak_W   = float(m.group(3)) * leak_scale
    return switch_W + int_W, leak_W


def _parse_timing_slack(path: str):
    """Return True/False/None for MET/VIOLATED/unknown timing slack from a DC timing report."""
    with open(path) as fh:
        text = fh.read()
    if re.search(r'slack\s*\(MET\)', text, re.IGNORECASE):
        return True
    if re.search(r'slack\s*\(VIOLATED\)', text, re.IGNORECASE):
        return False
    return None


def _parse_cacti_output(text: str):
    """Extract (read_J, write_J, leak_W) from CACTI stdout; return (None, None, None) on failure."""
    def find(patterns):
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return float(m.group(1))
        return None
    rd_nJ = find([
        r'Total dynamic read energy per access \(nJ\)\s*[:=]?\s*([\d.eE+\-]+)',
        r'Dynamic read energy \(nJ\)\s*[:=]?\s*([\d.eE+\-]+)',
    ])
    wr_nJ = find([
        r'Total dynamic write energy per access \(nJ\)\s*[:=]?\s*([\d.eE+\-]+)',
        r'Dynamic write energy \(nJ\)\s*[:=]?\s*([\d.eE+\-]+)',
    ])
    leak_mW = find([
        r'Total leakage power of a bank \(mW\)\s*[:=]?\s*([\d.eE+\-]+)',
        r'Standby leakage per bank\s*\(mW\)\s*[:=]?\s*([\d.eE+\-]+)',
        r'Total leakage \(mW\)\s*[:=]?\s*([\d.eE+\-]+)',
    ])
    if rd_nJ is None or wr_nJ is None or leak_mW is None:
        return None, None, None
    return rd_nJ * 1e-9, wr_nJ * 1e-9, leak_mW * 1e-3