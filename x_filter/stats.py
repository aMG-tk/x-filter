import numpy as np
import pandas as pd
import logging
from numba import njit, prange, set_num_threads
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import os
import tqdm
import multiprocessing as mp

# Set up logging
log = logging.getLogger("my_logger")
numba_logger = logging.getLogger("numba")
numba_logger.setLevel(logging.WARNING)


@njit(fastmath=True, cache=True)
def trim_coverage_by_subject(
    flattened_coverage: np.ndarray,
    start_positions: np.ndarray,
    subject_lengths: np.ndarray,
    avg_alignment_lengths: np.ndarray,
    trim_multiplier: float = 2,
    trim_offset: int = 10,
) -> None:
    for i in range(len(start_positions)):
        trim_length = (
            int(np.ceil(avg_alignment_lengths[i] / 2 * trim_multiplier)) + trim_offset
        )
        if trim_length >= subject_lengths[i]:
            continue
        start_idx, end_idx = start_positions[i], start_positions[i] + subject_lengths[i]
        flattened_coverage[start_idx : start_idx + trim_length] = 0
        flattened_coverage[end_idx - trim_length : end_idx] = 0


@njit(parallel=True, cache=True)
def compute_coverage_statistics(
    flattened_coverage: np.ndarray,
    start_positions: np.ndarray,
    subject_lengths: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    n_subjects = len(start_positions)
    mean_coverage = np.zeros(n_subjects, dtype=np.float32)
    std_coverage = np.zeros(n_subjects, dtype=np.float32)

    for i in prange(n_subjects):
        start_idx, end_idx = start_positions[i], start_positions[i] + subject_lengths[i]
        subject_coverage = flattened_coverage[start_idx:end_idx]
        mean = np.sum(subject_coverage) / subject_lengths[i]
        mean_coverage[i] = mean
        variance = np.sum((subject_coverage - mean) ** 2) / subject_lengths[i]
        std_coverage[i] = np.sqrt(variance)

    return mean_coverage, std_coverage


@njit(parallel=True, fastmath=True, cache=True)
def compute_alignment_statistics(
    alignment_lengths: np.ndarray,
    query_lengths: np.ndarray,
    percent_identity: np.ndarray,
    inverse_indices: np.ndarray,
    n_subjects: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sum_aln_len = np.zeros(n_subjects, dtype=np.float64)
    sum_sq_aln_len = np.zeros(n_subjects, dtype=np.float64)
    sum_read_len = np.zeros(n_subjects, dtype=np.float64)
    sum_sq_read_len = np.zeros(n_subjects, dtype=np.float64)
    sum_identity = np.zeros(n_subjects, dtype=np.float64)
    sum_sq_identity = np.zeros(n_subjects, dtype=np.float64)
    counts = np.zeros(n_subjects, dtype=np.int64)

    for i in prange(len(inverse_indices)):
        subject_idx = inverse_indices[i]
        aln_len = alignment_lengths[i]
        read_len = query_lengths[i]
        identity = percent_identity[i]

        sum_aln_len[subject_idx] += aln_len
        sum_sq_aln_len[subject_idx] += aln_len * aln_len
        sum_read_len[subject_idx] += read_len
        sum_sq_read_len[subject_idx] += read_len * read_len
        sum_identity[subject_idx] += identity
        sum_sq_identity[subject_idx] += identity * identity
        counts[subject_idx] += 1

    return (
        sum_aln_len,
        sum_sq_aln_len,
        sum_read_len,
        sum_sq_read_len,
        sum_identity,
        sum_sq_identity,
        counts,
    )


@njit(fastmath=True, cache=True)
def finalize_statistics(
    sum_vals: np.ndarray, sum_sq_vals: np.ndarray, counts: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    mean = np.zeros_like(sum_vals)
    std = np.zeros_like(sum_vals)
    mask = counts > 0
    mean[mask] = sum_vals[mask] / counts[mask]
    variance = np.maximum(sum_sq_vals[mask] / counts[mask] - mean[mask] ** 2, 0)
    std[mask] = np.sqrt(variance)
    return mean, std


@njit(fastmath=True, cache=True)
def update_coverage_array(
    flattened_coverage: np.ndarray,
    inverse_subject_indices: np.ndarray,
    subject_start_positions: np.ndarray,
    subject_end_positions: np.ndarray,
    start_positions: np.ndarray,
    subject_lengths: np.ndarray,
) -> None:
    n = len(inverse_subject_indices)
    fc_len = len(flattened_coverage)

    for i in range(n):
        subj_idx = inverse_subject_indices[i]
        start_pos = start_positions[subj_idx]
        subj_len = subject_lengths[subj_idx]
        start = start_pos + subject_start_positions[i]
        end = start_pos + min(subject_end_positions[i], subj_len - 1)
        if start < fc_len:
            flattened_coverage[start] += 1
        if end < fc_len:
            flattened_coverage[end] -= 1


@njit(parallel=True, cache=True)
def perform_cumulative_sum(
    flattened_coverage: np.ndarray,
    start_positions: np.ndarray,
    subject_lengths: np.ndarray,
) -> None:
    for subject_id in prange(len(start_positions)):
        start_idx, end_idx = (
            start_positions[subject_id],
            start_positions[subject_id] + subject_lengths[subject_id],
        )
        flattened_coverage[start_idx:end_idx] = np.cumsum(
            flattened_coverage[start_idx:end_idx]
        )


@njit(parallel=True, cache=True)
def compute_global_coverage_statistics(
    flattened_coverage: np.ndarray,
    start_positions: np.ndarray,
    subject_lengths: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    total_coverage = np.zeros(len(start_positions), dtype=np.int64)
    nonzero_coverage_counts = np.zeros(len(start_positions), dtype=np.int32)

    for i in prange(len(start_positions)):
        start_idx, end_idx = start_positions[i], start_positions[i] + subject_lengths[i]
        total_coverage[i] = np.sum(flattened_coverage[start_idx:end_idx])
        nonzero_coverage_counts[i] = np.count_nonzero(
            flattened_coverage[start_idx:end_idx]
        )

    return total_coverage, nonzero_coverage_counts


# def get_representative_indices(row_hashes: np.ndarray, num_threads: int) -> np.ndarray:
#     log.debug("Finding representative indices for unique hashes")
#     _, representative_indices = np.unique(row_hashes, return_index=True)
#     representative_indices.sort(kind="mergesort")
#     log.debug(f"Found {len(representative_indices)} unique hashes")
#     return representative_indices


@njit
def _find_unique_indices(chunk):
    seen = set()
    indices = np.empty(len(chunk), dtype=np.int64)
    count = 0
    for i in range(len(chunk)):
        if chunk[i] not in seen:
            seen.add(chunk[i])
            indices[count] = i
            count += 1
    return indices[:count]


def process_chunk(args):
    chunk, start_index = args
    local_indices = _find_unique_indices(chunk)
    return local_indices + start_index


def get_representative_indices(row_hashes: np.ndarray, num_threads: int) -> np.ndarray:
    chunk_size = len(row_hashes) // num_threads
    chunks = [
        (row_hashes[i : i + chunk_size], i)
        for i in range(0, len(row_hashes), chunk_size)
    ]

    with mp.Pool(num_threads) as pool:
        results = pool.map(process_chunk, chunks)

    representative_indices = np.concatenate(results)
    representative_indices.sort(kind="mergesort")

    return representative_indices


# Alternative implementation using only Numba
@njit(parallel=True)
def get_representative_indices_numba(row_hashes: np.ndarray) -> np.ndarray:
    seen = set()
    indices = np.empty(len(row_hashes), dtype=np.int64)
    count = 0
    for i in prange(len(row_hashes)):
        if row_hashes[i] not in seen:
            seen.add(row_hashes[i])
            indices[count] = i
            count += 1
    return np.sort(indices[:count])


def write_and_flush(mmap_array, data):
    mmap_array[:] = data
    mmap_array.flush()


def initialize_mmap_arrays(mmap_folder, unique_subjects, max_subject_lengths):
    log.debug("Initializing optimized memory-mapped arrays")
    os.makedirs(mmap_folder, exist_ok=True)
    cumsum = np.concatenate(([0], np.cumsum(max_subject_lengths[:-1])))
    start_positions_file = f"{mmap_folder}/start_positions.dat"
    subject_lengths_file = f"{mmap_folder}/subject_lengths.dat"

    start_positions = np.memmap(
        start_positions_file, dtype=np.int64, mode="w+", shape=(len(unique_subjects),)
    )
    subject_lengths_mmap = np.memmap(
        subject_lengths_file, dtype=np.int32, mode="w+", shape=(len(unique_subjects),)
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_start = executor.submit(write_and_flush, start_positions, cumsum)
        future_lengths = executor.submit(
            write_and_flush, subject_lengths_mmap, max_subject_lengths
        )
        future_start.result()
        future_lengths.result()

    log.debug("Memory-mapped arrays initialization completed")
    return start_positions, subject_lengths_mmap


def slice_mmap(arr, arr_name, indices, mmap_folder, dtype, shape):
    mmap_path = os.path.join(mmap_folder, f"{arr_name}.npy")
    sliced_arr = np.memmap(mmap_path, dtype=dtype, mode="w+", shape=(shape,))
    np.take(arr, indices, out=sliced_arr)
    del sliced_arr  # Close the memmap file


def slice_mmap_wrapper(args):
    arr, arr_name, dtype, indices, mmap_folder, shape = args
    return slice_mmap(arr, arr_name, indices, mmap_folder, dtype, shape)


def parallel_slice_mmap(
    numpy_arrays, representative_indices, mmap_folder, num_threads=1
):
    os.makedirs(mmap_folder, exist_ok=True)

    arrays_to_process = [
        (numpy_arrays["subject_numeric_id"], "subject_numeric_id", np.int64),
        (numpy_arrays["subjectStart"], "subjectStart", np.int32),
        (numpy_arrays["subjectEnd"], "subjectEnd", np.int32),
        (numpy_arrays["alnLength"], "alnLength", np.int32),
        (numpy_arrays["qlen"], "qlen", np.int32),
        (numpy_arrays["percIdentity"], "percIdentity", np.float32),
        (numpy_arrays["slen"], "slen", np.int32),
        (numpy_arrays["bitScore"], "bitScore", np.float32),
        (numpy_arrays["query_numeric_id"], "query_numeric_id", np.int64),
        (numpy_arrays["row_hash"], "row_hash", np.int64),
    ]

    args_list = [
        (
            arr,
            name,
            dtype,
            representative_indices,
            mmap_folder,
            len(representative_indices),
        )
        for arr, name, dtype in arrays_to_process
    ]

    with ProcessPoolExecutor(max_workers=num_threads) as executor:
        list(
            tqdm.tqdm(
                executor.map(slice_mmap_wrapper, args_list),
                total=len(arrays_to_process),
                desc="Removing duplicates",
                leave=False,
                ncols=80,
            )
        )

    # Load memmapped arrays
    for _, name, dtype in arrays_to_process:
        mmap_path = os.path.join(mmap_folder, f"{name}.npy")
        numpy_arrays[name] = np.memmap(mmap_path, dtype=dtype, mode="r")

    return numpy_arrays


def calculate_alignment_statistics(
    alignment_lengths: np.ndarray,
    query_lengths: np.ndarray,
    percent_identity: np.ndarray,
    inverse_indices: np.ndarray,
    n_subjects: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    log.debug("Calculating alignment statistics")
    (
        sum_aln_len,
        sum_sq_aln_len,
        sum_read_len,
        sum_sq_read_len,
        sum_identity,
        sum_sq_identity,
        counts,
    ) = compute_alignment_statistics(
        alignment_lengths, query_lengths, percent_identity, inverse_indices, n_subjects
    )

    avg_aln_len, std_aln_len = finalize_statistics(sum_aln_len, sum_sq_aln_len, counts)
    avg_read_len, std_read_len = finalize_statistics(
        sum_read_len, sum_sq_read_len, counts
    )
    avg_identity, std_identity = finalize_statistics(
        sum_identity, sum_sq_identity, counts
    )

    return (
        avg_aln_len,
        std_aln_len,
        avg_read_len,
        std_read_len,
        avg_identity,
        std_identity,
    )


def calculate_statistics(
    numpy_arrays: dict, temp_files: dict, num_threads: int = 1, rm_dups: bool = True
) -> pd.DataFrame:
    mmap_folder = temp_files["mmap"]
    set_num_threads(num_threads)

    # Extract arrays from numpy_arrays dictionary
    subject_ids = numpy_arrays["subject_numeric_id"]
    subject_start_positions = numpy_arrays["subjectStart"]
    subject_end_positions = numpy_arrays["subjectEnd"]
    alignment_lengths = numpy_arrays["alnLength"]
    query_lengths = numpy_arrays["qlen"]
    percent_identity = numpy_arrays["percIdentity"]
    subject_lengths = numpy_arrays["slen"]
    if rm_dups:
        row_hashes = numpy_arrays["row_hash"]

    steps = [
        "Identifying unique subjects, hashes, and selecting representatives",
        "Saving dereplicated mmap arrays",
        "Finding unique subjects and inverse indices",
        "Calculating maximum subject length for each unique subject",
        "Initializing coverage array",
        "Initializing memory-mapped arrays",
        "Updating coverage",
        "Performing cumulative sum on coverage array",
        "Calculating alignment statistics",
        "Trimming coverage",
        "Calculating global coverage statistics",
        "Calculating average depth",
        "Calculating coverage mean and standard deviation",
        "Calculating depth evenness",
    ]

    steps = steps[: len(steps) - 1] if rm_dups else steps

    with tqdm.tqdm(
        total=len(steps), desc="Processing steps", leave=False, ncols=80
    ) as pbar:
        if rm_dups:
            log.debug(
                "Step 1: Identifying unique subjects, hashes, and selecting representatives"
            )
            representative_indices = get_representative_indices(
                row_hashes, num_threads=num_threads
            )
            pbar.update(1)

            log.debug("Step 2: Saving dereplicated mmap arrays")
            numpy_arrays = parallel_slice_mmap(
                numpy_arrays,
                representative_indices,
                mmap_folder,
                num_threads=num_threads,
            )
        subject_ids = numpy_arrays["subject_numeric_id"]
        subject_start_positions = numpy_arrays["subjectStart"]
        subject_end_positions = numpy_arrays["subjectEnd"]
        alignment_lengths = numpy_arrays["alnLength"]
        query_lengths = numpy_arrays["qlen"]
        percent_identity = numpy_arrays["percIdentity"]
        subject_lengths = numpy_arrays["slen"]
        if rm_dups:
            del representative_indices
        pbar.update(1)

        log.debug("Step 3: Finding unique subjects and inverse indices")
        unique_subjects, inverse_indices = np.unique(subject_ids, return_inverse=True)
        pbar.update(1)

        log.debug("Step 4: Calculating maximum subject length for each unique subject")
        max_subject_lengths = np.zeros(
            len(unique_subjects), dtype=subject_lengths.dtype
        )
        np.maximum.at(max_subject_lengths, inverse_indices, subject_lengths)
        pbar.update(1)

        total_positions = np.sum(max_subject_lengths)
        log.debug(f"Total positions in coverage array: {total_positions}")

        log.debug("Step 5: Initializing coverage array")
        flattened_coverage = np.zeros(total_positions, dtype=np.int32)
        pbar.update(1)

        log.debug("Step 6: Initializing memory-mapped arrays")
        start_positions, subject_lengths_mmap = initialize_mmap_arrays(
            mmap_folder, unique_subjects, max_subject_lengths
        )
        pbar.update(1)

        log.debug("Step 7: Updating coverage")
        update_coverage_array(
            flattened_coverage,
            inverse_indices,
            subject_start_positions,
            subject_end_positions,
            start_positions,
            subject_lengths_mmap,
        )
        pbar.update(1)

        log.debug("Step 8: Performing cumulative sum on coverage array")
        perform_cumulative_sum(
            flattened_coverage, start_positions, subject_lengths_mmap
        )
        pbar.update(1)

        log.debug("Step 9: Calculating alignment statistics")
        n_subjects = len(unique_subjects)
        (
            avg_aln_len,
            std_aln_len,
            avg_read_len,
            std_read_len,
            avg_identity,
            std_identity,
        ) = calculate_alignment_statistics(
            alignment_lengths,
            query_lengths,
            percent_identity,
            inverse_indices,
            n_subjects,
        )
        pbar.update(1)

        num_alignments = np.bincount(inverse_indices, minlength=n_subjects)

        log.debug("Step 10: Trimming coverage")
        trim_coverage_by_subject(
            flattened_coverage, start_positions, subject_lengths_mmap, avg_aln_len
        )
        pbar.update(1)

        log.debug("Step 11: Calculating global coverage statistics")
        total_coverage, nonzero_coverage_counts = compute_global_coverage_statistics(
            flattened_coverage, start_positions, subject_lengths_mmap
        )
        pbar.update(1)

        log.debug("Step 12: Calculating average depth")
        avg_depth = np.zeros_like(total_coverage, dtype=np.float32)
        valid_mask = nonzero_coverage_counts > 0
        avg_depth[valid_mask] = (
            total_coverage[valid_mask] / nonzero_coverage_counts[valid_mask]
        )
        pbar.update(1)

        log.debug("Step 13: Calculating coverage mean and standard deviation")
        mean_coverage, std_coverage = compute_coverage_statistics(
            flattened_coverage, start_positions, subject_lengths_mmap
        )
        pbar.update(1)

        log.debug("Step 14: Calculating depth evenness")
        depth_evenness = np.zeros_like(mean_coverage, dtype=np.float32)
        valid_coverage_mask = (mean_coverage > 0) & (~np.isnan(mean_coverage))
        depth_evenness[valid_coverage_mask] = (
            std_coverage[valid_coverage_mask] / mean_coverage[valid_coverage_mask]
        )
        depth_evenness[~valid_coverage_mask] = np.nan
        pbar.update(1)

    final_stats = pd.DataFrame(
        {
            "subject_numeric_id": unique_subjects,
            "avg_alignment_length": avg_aln_len,
            "num_alignments": num_alignments,
            "avg_read_length": avg_read_len,
            "std_read_length": std_read_len,
            "avg_identity": avg_identity,
            "std_identity": std_identity,
            "total_covered_bases": nonzero_coverage_counts,
            "total_depth": total_coverage,
            "subject_length": max_subject_lengths,
            "breadth": nonzero_coverage_counts / max_subject_lengths,
            "avg_depth": avg_depth,
            "mean_coverage": mean_coverage,
            "std_coverage": std_coverage,
            "depth_evenness": depth_evenness,
        }
    )

    log.debug("Final DataFrame with computed statistics ready")
    return final_stats, unique_subjects, inverse_indices, numpy_arrays
