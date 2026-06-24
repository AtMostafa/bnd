"""I/O helpers for pyaldata MATLAB files.

pyaldata sessions are written as a single **MATLAB v7.3** (HDF5) file. Unlike the
legacy v5 format, v7.3 has no 2 GB-per-file limit, so the whole session is stored
as one struct array and there is no need to partition trials across several files.
Read the file back with ``pyaldata.mat2dataframe`` (which uses ``hdf5storage`` for
v7.3) or any HDF5-aware MATLAB reader.
"""

from pathlib import Path

import numpy as np
import hdf5storage


def save_pyaldata_mat(data_array: np.recarray, path: "str | Path") -> None:
    """Write a pyaldata struct array to a single MATLAB v7.3 ``.mat`` file.

    Parameters
    ----------
    data_array : np.recarray
        One record per trial, e.g. ``DataFrame.to_records(index=False)``.
    path : str | Path
        Destination ``.mat`` path.
    """
    if len(data_array) < 1:
        raise ValueError("Empty pyaldata: no trials to save.")

    hdf5storage.savemat(
        str(path),
        {"pyaldata": data_array},
        format="7.3",
        matlab_compatible=True,
        truncate_existing=True,
        compress=False
    )
