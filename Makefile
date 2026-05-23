# Makefile — place at SC repo root
# Drives the analytical modeling pipeline via uv.

# Directory containing the analytical modeling scripts
AM_DIR := analytical_modeling

# uv run prefix — ensures the project venv is used
PY := uv run python

.PHONY: help sync compare validate clean

help:
	@echo "Targets:"
	@echo "  make sync      - install/update dependencies from uv.lock"
	@echo "  make compare   - run the energy comparison driver"
	@echo "  make validate  - run the binary model validation against SCALE-Sim"
	@echo "  make clean     - remove generated outputs"

# Install dependencies (run after cloning, or after pyproject changes)
sync:
	uv sync

# Run the main comparison driver
compare:
	cd $(AM_DIR) && $(PY) compare.py

# Run the SCALE-Sim validation
validate:
	cd $(AM_DIR) && $(PY) validate.py

# Clean generated artifacts
clean:
	rm -rf $(AM_DIR)/outputs
	rm -rf $(AM_DIR)/configs/binary_64x64.cfg
	rm -rf $(AM_DIR)/topologies/compare_shapes.csv
	rm -rf $(AM_DIR)/layouts/stub_layout.csv
	find $(AM_DIR) -name "__pycache__" -type d -exec rm -rf {} +