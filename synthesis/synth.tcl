################################################################################
# synth.tcl - Generic Synopsys Design Compiler synthesis script
#
# The top module is passed in from the Makefile via the TOP environment
# variable (preferred) or via a pre-set "TOP" tcl variable (dc_shell -x).
#
# Run standalone with:  dc_shell -f synth.tcl -x "set TOP and_module"
################################################################################

# ---------------------------------------------------------------------------
# 1. Resolve the top module name
# ---------------------------------------------------------------------------
if {![info exists TOP]} {
    if {[info exists ::env(TOP)]} {
        set TOP $::env(TOP)
    } else {
        echo "ERROR: No top module specified. Set TOP env var or use -x \"set TOP <name>\"."
        exit 1
    }
}
echo "INFO: Synthesizing top module: $TOP"

# ---------------------------------------------------------------------------
# 2. Directories  (override from the Makefile by exporting these env vars)
# ---------------------------------------------------------------------------
set RTL_DIR     [expr {[info exists ::env(RTL_DIR)]     ? $::env(RTL_DIR)     : "."}]
set OUTPUT_DIR  [expr {[info exists ::env(OUTPUT_DIR)]  ? $::env(OUTPUT_DIR)  : "./output"}]
set REPORTS_DIR [expr {[info exists ::env(REPORTS_DIR)] ? $::env(REPORTS_DIR) : "./reports"}]

file mkdir $OUTPUT_DIR
file mkdir $REPORTS_DIR

# ---------------------------------------------------------------------------
# 3. Technology library setup  --  set LIB in the Makefile or env
# ---------------------------------------------------------------------------
set target_library [expr {[info exists ::env(LIB)] ? $::env(LIB) : "lib/gscl45nm.db"}]
set link_library   "* $target_library"

# ---------------------------------------------------------------------------
# 4. Read & elaborate the RTL
# ---------------------------------------------------------------------------
# Prefer .sv; fall back to .v for legacy files.
if {[file exists "$RTL_DIR/$TOP.sv"]} {
    set rtl_file "$RTL_DIR/$TOP.sv"
    set rtl_fmt  sverilog
} elseif {[file exists "$RTL_DIR/$TOP.v"]} {
    set rtl_file "$RTL_DIR/$TOP.v"
    set rtl_fmt  verilog
} else {
    echo "ERROR: no RTL file found for $TOP in $RTL_DIR"
    exit 1
}
if {![analyze -format $rtl_fmt $rtl_file]} {
    echo "ERROR: analyze failed for $rtl_file"
    exit 1
}
if {![elaborate $TOP]} {
    echo "ERROR: elaborate failed for $TOP"
    exit 1
}

current_design $TOP
link
uniquify

# ---------------------------------------------------------------------------
# 5. Constraints  --  tweak for your design
# ---------------------------------------------------------------------------
set CLK_PORT   "clk"
set CLK_PERIOD 10.0   ;# ns

# Only create a clock if the design actually has the clock port
if {[sizeof_collection [get_ports -quiet $CLK_PORT]] > 0} {
    create_clock -name $CLK_PORT -period $CLK_PERIOD [get_ports $CLK_PORT]
    set_clock_uncertainty 0.1 [get_clocks $CLK_PORT]
    set_input_delay  2.0 -clock $CLK_PORT [remove_from_collection [all_inputs] [get_ports $CLK_PORT]]
    set_output_delay 2.0 -clock $CLK_PORT [all_outputs]
} else {
    echo "INFO: No port '$CLK_PORT' found - treating $TOP as purely combinational."
}

set_max_area 0

# ---------------------------------------------------------------------------
# 6. Compile
# ---------------------------------------------------------------------------
set area_effort  [expr {[info exists ::env(AREA_EFFORT)]  ? $::env(AREA_EFFORT)  : "medium"}]
set power_effort [expr {[info exists ::env(POWER_EFFORT)] ? $::env(POWER_EFFORT) : "high"}]
set map_effort   [expr {[info exists ::env(MAP_EFFORT)]   ? $::env(MAP_EFFORT)   : "low"}]

echo "INFO: compile -area_effort $area_effort -map_effort $map_effort -power_effort $power_effort"
compile -area_effort $area_effort -map_effort $map_effort -power_effort $power_effort
# Alternatively, use compile_ultra for more aggressive optimization (ignores the effort flags above):
# compile_ultra

# ---------------------------------------------------------------------------
# 7. Write outputs
# ---------------------------------------------------------------------------
change_names -rules verilog -hierarchy
write -format verilog -hierarchy -output "$OUTPUT_DIR/${TOP}_netlist.v"
write -format ddc      -hierarchy -output "$OUTPUT_DIR/${TOP}.ddc"
write_sdc                          "$OUTPUT_DIR/${TOP}.sdc"

# ---------------------------------------------------------------------------
# 8. Reports
# ---------------------------------------------------------------------------
redirect "$REPORTS_DIR/${TOP}_timing.rpt"     { report_timing -max_paths 10 }
redirect "$REPORTS_DIR/${TOP}_area.rpt"       { report_area -hierarchy }
redirect "$REPORTS_DIR/${TOP}_power.rpt"      { report_power -hier }
redirect "$REPORTS_DIR/${TOP}_qor.rpt"        { report_qor }
redirect "$REPORTS_DIR/${TOP}_constraint.rpt" { report_constraint -all_violators }

echo "INFO: Synthesis of $TOP complete. See $OUTPUT_DIR and $REPORTS_DIR."
exit 0