SHELL := bash
################################################################################
# Makefile — SC repo root
#
# Two pipelines in one file:
#   1. Synopsys Design Compiler synthesis  (make <module>)
#   2. Analytical modeling pipeline via uv (make sync|compare|validate)
#
# Synthesis layout:
#   ./Makefile                  <- this file
#   ./synthesis/synth.tcl       <- DC script
#   ./synthesis/verilog/        <- RTL source (.v files)
#   ./synthesis/output/         <- all generated synthesis output
################################################################################

# ===== Synthesis config =======================================================
DC          := dc_shell
SYNTH_TCL   := synth.tcl
# Synthesis folder
SYN_DIR     := synthesis
# Relative to SYN_DIR, exported for synth.tcl to read.
export RTL_DIR     := verilog
export OUTPUT_DIR  := output
export REPORTS_DIR := reports

# --- Synthesis knobs (override on the command line) --------------------------
#   make and_module LIB=/path/to/stdcell.db AREA_EFFORT=high POWER_EFFORT=high
#
#   LIB           target technology .db file(s). Space-separated for multiple
#                 (quote it: LIB="a.db b.db").
#   AREA_EFFORT   none | low | medium | high   (DC compile -area_effort)
#   POWER_EFFORT  none | low | high            (DC compile -power_effort)
#   MAP_EFFORT    low  | medium | high         (DC compile -map_effort)
#
# '?=' means an environment value or command-line override wins over these.
export LIB          ?= lib/gscl45nm.db
export AREA_EFFORT  ?= medium
export POWER_EFFORT ?= high
export MAP_EFFORT   ?= low

# ===== Analytical modeling config ============================================
# Directory containing the analytical modeling scripts
AM_DIR := analytical_modeling
# uv run prefix — ensures the project venv is used
PY := uv run python

.PHONY: help sync compare validate clean

# ===== Help ===================================================================
help:
	@echo "Synthesis:"
	@echo "  make <module>   Synthesize synthesis/verilog/<module>.sv  (e.g. make and_gate)"
	@echo "    Knobs (override on command line):"
	@echo "      LIB=<.db>            target library  (current: $(LIB))"
	@echo "      AREA_EFFORT=<level>  none|low|medium|high  (current: $(AREA_EFFORT))"
	@echo "      POWER_EFFORT=<level> none|low|high         (current: $(POWER_EFFORT))"
	@echo "      MAP_EFFORT=<level>   low|medium|high        (current: $(MAP_EFFORT))"
	@echo "    e.g.  make and_module LIB=/pdk/sc.db AREA_EFFORT=high POWER_EFFORT=high"
	@echo ""
	@echo "Analytical modeling:"
	@echo "  make sync       Install/update dependencies from uv.lock"
	@echo "  make compare    Run the energy comparison driver (all default workloads)"
	@echo "  make validate   Run the binary model validation against SCALE-Sim"
	@echo ""
	@echo "  compare.py arguments (pass via ARGS='...'):"
	@echo "    make compare ARGS='-M 128 -N 128 -K 64'"
	@echo "      -M <int>              Override workload M dimension"
	@echo "      -N <int>              Override workload N dimension"
	@echo "      -K <int>              Override workload K dimension"
	@echo "      --array-h <int>       PE array height  (default: 64)"
	@echo "      --array-w <int>       PE array width   (default: 64)"
	@echo "      --precision <int>     Bit precision    (default: 8)"
	@echo "      --clock <float>       Clock period (s) (default: 1e-9)"
	@echo "      --synthesize          Run DC synthesis to populate energy values"
	@echo ""
	@echo "General:"
	@echo "  make clean      Remove all generated outputs (synthesis + modeling)"
	@echo "  make help       Show this message"

# ===== Synthesis ==============================================================
# `make <module>` synthesizes synthesis/verilog/<module>.v.
# DC runs from inside SYN_DIR so its WORK/, command.log, etc. stay contained.
# Explicit targets above (sync/compare/validate/clean/help) override this rule.
%: $(SYN_DIR)/$(RTL_DIR)/%.sv $(SYN_DIR)/$(SYNTH_TCL)
	@mkdir -p $(SYN_DIR)/$(OUTPUT_DIR)
	@echo ">> Synthesizing module '$*' from $<"
	@echo ">>   LIB=$(LIB)  AREA_EFFORT=$(AREA_EFFORT)  POWER_EFFORT=$(POWER_EFFORT)  MAP_EFFORT=$(MAP_EFFORT)"
	@cd $(SYN_DIR) && TOP=$* $(DC) -f $(SYNTH_TCL) -x "set TOP $*" \
		| tee $(OUTPUT_DIR)/$*.log; exit $${PIPESTATUS[0]}
	@echo ">> Done. See $(SYN_DIR)/$(OUTPUT_DIR)/"

# ===== Analytical modeling ====================================================
# Install dependencies (run after cloning, or after pyproject changes)
sync:
	uv sync

ARGS ?=

# Run the main comparison driver
compare:
	cd $(AM_DIR) && $(PY) compare.py $(ARGS)

# Run the SCALE-Sim validation
validate:
	cd $(AM_DIR) && $(PY) validate.py

# ===== Clean (both pipelines) =================================================
clean:
	@# --- synthesis artifacts ---
	rm -rf $(SYN_DIR)/$(OUTPUT_DIR) \
		$(SYN_DIR)/$(REPORTS_DIR) \
		$(SYN_DIR)/command.log $(SYN_DIR)/default.svf \
		$(SYN_DIR)/*.syn $(SYN_DIR)/*.mr $(SYN_DIR)/*.pvl $(SYN_DIR)/WORK
	@# --- analytical modeling artifacts ---
	rm -rf $(AM_DIR)/outputs
	rm -rf $(AM_DIR)/configs/binary_64x64.cfg
	rm -rf $(AM_DIR)/topologies/compare_shapes.csv
	rm -rf $(AM_DIR)/layouts/stub_layout.csv
	find $(AM_DIR) -name "__pycache__" -type d -exec rm -rf {} +
	@echo ">> Cleaned generated files."