"""TEMP test: verify the v5 -> v7.3 pyaldata save change is loss-less.

Loads a real session's pyaldata DataFrame (the "pre-change" df, as currently
loaded from the legacy v5 ``.mat``/``.p`` files), re-saves it with the new
``bnd.pipeline.mat_io.save_pyaldata_mat`` (single MATLAB v7.3 file), reloads it
exactly the way ``session.pyal`` would (``pyaldata.mat2dataframe`` -> mat73
fallback) to get the "post-change" df, then compares **every column of a random
trial** and asserts they are identical.

Run with the analysis venv (has hdf5storage / mat73 / pyaldata / opbci):
    /home/msafaie/repos/decorrelation-bci/.venv/bin/python tests/test_v73_roundtrip_temp.py

This file is temporary and can be deleted once the change is validated.
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

SESSION = sys.argv[1] if len(sys.argv) > 1 else "M115_2026_04_10_10_30"
ANIMAL = SESSION.split("_")[0]
SESSION_DIR = Path("/data/raw") / ANIMAL / SESSION
SCRATCH = Path(
    "/tmp/claude-1547056/-home-msafaie-repos-decorrelation-bci/"
    "4baf62dd-7161-4caf-8f5d-60852ccee9b7/scratchpad"
)
V73_PATH = SCRATCH / f"{SESSION}_pyaldata.mat"   # written by the NEW bnd writer
SEED = 12345


def _load_save_fn():
    """Import the new writer straight from the file (no pynwb / bnd package init)."""
    p = Path(__file__).resolve().parents[1] / "bnd" / "pipeline" / "mat_io.py"
    spec = importlib.util.spec_from_file_location("bnd_mat_io", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.save_pyaldata_mat


def _cells_equal(a, b):
    """Return (equal, pre_dtype, post_dtype, note) for two DataFrame cell values."""
    aa, bb = np.asarray(a), np.asarray(b)
    dt = (str(aa.dtype), str(bb.dtype))
    if aa.shape != bb.shape:
        return False, dt[0], dt[1], f"shape {aa.shape} != {bb.shape}"
    if aa.size == 0:
        return True, dt[0], dt[1], "empty"
    try:
        # numeric (incl. object arrays holding numbers/NaN): NaN-aware compare
        eq = np.array_equal(
            aa.astype(np.float64), bb.astype(np.float64), equal_nan=True
        )
    except (ValueError, TypeError):
        # non-numeric (strings / mixed objects): compare as strings
        eq = np.array_equal(aa.astype(str), bb.astype(str))
    return bool(eq), dt[0], dt[1], ""


def main():
    import pyaldata as pyal
    from opbci import dataTools

    save_pyaldata_mat = _load_save_fn()

    print(f"[1/4] loading PRE-change df (legacy load) for {SESSION} ...", flush=True)
    df_pre = dataTools.load_pyal_data(SESSION_DIR)
    print(f"      pre: {len(df_pre)} trials, {df_pre.shape[1]} columns", flush=True)

    print(f"[2/4] re-saving as MATLAB v7.3 via new writer -> {V73_PATH.name} ...", flush=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    save_pyaldata_mat(df_pre.to_records(index=False), V73_PATH)
    print(f"      wrote {V73_PATH.stat().st_size / 2**30:.2f} GB", flush=True)

    print("[3/4] reloading POST-change df the way session.pyal would ...", flush=True)
    df_post = pyal.mat2dataframe(V73_PATH, shift_idx_fields=False)
    print(f"      post: {len(df_post)} trials, {df_post.shape[1]} columns", flush=True)

    print("[4/4] comparing a random trial, column by column ...", flush=True)
    assert len(df_pre) == len(df_post), (len(df_pre), len(df_post))
    assert set(df_pre.columns) == set(df_post.columns), (
        set(df_pre.columns) ^ set(df_post.columns)
    )

    rng = np.random.default_rng(SEED)
    ti = int(rng.integers(len(df_pre)))
    r_pre, r_post = df_pre.iloc[ti], df_post.iloc[ti]
    print(f"      trial index = {ti}  (trial_id={r_pre.get('trial_id')}, "
          f"name={r_pre.get('trial_name')}, length={r_pre.get('trial_length')})\n", flush=True)

    rows, all_ok, dtype_diffs = [], True, 0
    print(f"      {'column':28s} {'equal':6s} {'pre_dtype':14s} {'post_dtype':14s} note")
    print("      " + "-" * 78)
    for col in df_pre.columns:
        eq, dpre, dpost, note = _cells_equal(r_pre[col], r_post[col])
        all_ok &= eq
        if dpre != dpost:
            dtype_diffs += 1
        flag = "OK" if eq else "FAIL"
        print(f"      {col:28s} {flag:6s} {dpre:14s} {dpost:14s} {note}")
        rows.append(dict(column=col, equal=eq, pre_dtype=dpre, post_dtype=dpost, note=note))

    summary = dict(session=SESSION, trial_index=ti, n_trials=len(df_pre),
                   n_columns=len(df_pre.columns), all_values_equal=all_ok,
                   dtype_diffs=dtype_diffs, columns=rows)
    (SCRATCH / f"v73_roundtrip_{SESSION}.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n      " + "=" * 60)
    print(f"      ALL COLUMNS VALUE-EQUAL: {all_ok}   (dtype-only diffs: {dtype_diffs})")
    print("      " + "=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
