"""SRAM access-count formulas as a function of dataflow.

For C[M,N] = A[M,K] . B[K,N] tiled onto an H x W array, the operand that is
*stationary* is read once and reused; the moving operands are re-streamed per
tile, so their access counts pick up tile-count multipliers. The stationary
operand flips with the dataflow:

    'ws' (weight-stationary)  : B held in array. Filter read ~once; A and C move.
    'os' (output-stationary)  : C accumulated in place. Output written once;
                                A and B both re-streamed per output tile.
    'is' (input-stationary)   : A held in array. Ifmap read ~once; B and C move.

These return ELEMENT counts. Convert to physical (access-width) counts in the
arch model using the SRAM's access width:
    accesses = ceil(element_count / (access_bytes / element_bytes))

Binary WS counts here match the SCALE-Sim-validated BinarySystolic model.
Each architecture should select the dataflow that matches what ITS paper
describes; the differences between architectures are real, not bugs.
"""
from math import ceil


def sram_access_counts(dataflow, M, N, K, array_h, array_w):
    """Return element-count dict for one GEMM on an array_h x array_w array.

    Keys: filter_reads, ifmap_reads, ofmap_writes  (element counts)
    """
    df = dataflow.lower()
    h_tiles = ceil(M / array_h)   # tiles along M (output rows)
    w_tiles = ceil(N / array_w)   # tiles along N (output cols)
    k_tiles = ceil(K / array_h)   # tiles along K when K maps onto array rows

    if df == 'ws':
        # Weight-stationary: B loaded once per (K-tile, N-tile); A re-streamed
        # once per N-tile; C partial sums written per K-tile.
        # Matches the SCALE-Sim-validated binary systolic model.
        return {
            'filter_reads': K * N,                 # each weight read once
            'ifmap_reads':  M * K * w_tiles,       # A re-read per N-tile
            'ofmap_writes': M * N * k_tiles,       # partial-sum spills per K-tile
        }

    elif df == 'os':
        # Output-stationary: each output accumulates in place -> written once,
        # no partial-sum spills. A and B are both streamed in for every output
        # tile, so each is re-read once per the *other* dimension's tiles.
        return {
            'filter_reads': K * N * h_tiles,       # B re-read per M-tile
            'ifmap_reads':  M * K * w_tiles,       # A re-read per N-tile
            'ofmap_writes': M * N,                 # each output written once
        }

    elif df == 'is':
        # Input-stationary: A held in array, read once. B re-streamed; C spills.
        return {
            'filter_reads': K * N * h_tiles,       # B re-read per M-tile
            'ifmap_reads':  M * K,                 # each input read once
            'ofmap_writes': M * N * k_tiles,       # partial-sum spills per K-tile
        }

    elif df == 'ugemm':
        # uGEMM fully-parallel broadcast, K accumulates fully in-PE (no K-tiles,
        # no partial-sum spill). M,N tile onto the array. Each output written
        # once. Weights re-read per M-tile, inputs re-read per N-tile.
        return {
            'filter_reads': K * N * h_tiles,
            'ifmap_reads':  M * K * w_tiles,
            'ofmap_writes': M * N,
        }

    else:
        raise ValueError(f"Unknown dataflow: {dataflow!r} "
                         f"(expected 'ws', 'os', 'is', or 'ugemm')")


def to_physical_accesses(element_count, access_bytes, element_bytes):
    """Convert an element count to physical accesses of `access_bytes` width."""
    elems_per_access = max(1, access_bytes // element_bytes)
    return ceil(element_count / elems_per_access)