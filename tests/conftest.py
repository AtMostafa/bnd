"""
Shared fake data tree for the target-resolution tests.

local/raw                                remote/raw
  M001/ A1, A2                             M001/ A1, A2 (ephys), A3 (ephys, remote-only)
  M002/ B1                                 M002/ B1
  R001/ R1   (animal name not starting M)  R001/ R1
  M003/      (animal with no sessions)
"""

from unittest.mock import patch

import pytest

from bnd.config import Config

A1 = "M001_2024_01_01_10_00"
A2 = "M001_2024_02_01_10_00"
A3 = "M001_2024_03_01_10_00"  # remote only
B1 = "M002_2024_01_05_09_00"
R1 = "R001_2024_03_01_12_00"

LOCAL_SESSIONS = [A1, A2, B1, R1]
REMOTE_SESSIONS = [A1, A2, A3, B1, R1]
EPHYS_SESSIONS = [A2, A3]  # on remote


@pytest.fixture
def config(tmp_path):
    for s in LOCAL_SESSIONS:
        (tmp_path / "local/raw" / s[:4] / s).mkdir(parents=True)
    (tmp_path / "local/raw/M003").mkdir()
    for s in REMOTE_SESSIONS:
        (tmp_path / "remote/raw" / s[:4] / s).mkdir(parents=True)
    for s in EPHYS_SESSIONS:
        (tmp_path / "remote/raw" / s[:4] / s / f"{s}_g0").mkdir()

    env = tmp_path / ".env"
    env.write_text(f"LOCAL_PATH = {tmp_path / 'local'}\nREMOTE_PATH = {tmp_path / 'remote'}\n")
    cfg = Config(env)
    with (
        patch("bnd.config._load_config", return_value=cfg),
        patch("bnd.resolve._load_config", return_value=cfg),
        patch("bnd.cli._load_config", return_value=cfg),
    ):
        yield cfg
