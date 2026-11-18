"""
Every CLI command fed animals, sessions, and combinations of both.

Downstream work (upload, download, conversion, kilosort) is mocked: these tests check
*which sessions* each command acts on, not the processing itself.
"""

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from bnd.cli import app

from .conftest import A1, A2, A3, B1, R1

runner = CliRunner()

# Input shapes shared by all commands: (id, args)
SHAPES = {
    "one animal": ["M001"],
    "several animals": ["M001", "M002", "R001"],
    "one session": [A1],
    "several sessions": [B1, A1],
    "animal + session": ["M002", A1],
    "session + its own animal": [A1, "M001"],
    "mixed, interleaved": ["M001", B1, "R001", A2],
    "duplicates": ["M002", "M002", B1],
    "invalid + valid": ["M009", "abc", B1],
}


def _expected(config_kind: str, shape: str) -> list[str]:
    """Sessions a command should act on, per resolution rule."""
    return {
        # local, animal -> all sessions (to-pyal, to-nwb, ksort)
        "local_all": {
            "one animal": [A1, A2],
            "several animals": [A1, A2, B1, R1],
            "one session": [A1],
            "several sessions": [B1, A1],
            "animal + session": [B1, A1],
            "session + its own animal": [A1, A2],
            "mixed, interleaved": [A1, A2, B1, R1],
            "duplicates": [B1],
            "invalid + valid": [B1],
        },
        # local, animal -> last session (up)
        "local_last": {
            "one animal": [A2],
            "several animals": [A2, B1, R1],
            "one session": [A1],
            "several sessions": [B1, A1],
            "animal + session": [B1, A1],
            "session + its own animal": [A1, A2],
            "mixed, interleaved": [A2, B1, R1],
            "duplicates": [B1],
            "invalid + valid": [B1],
        },
        # remote, animal -> all sessions (dl, dl-light)
        "remote_all": {
            "one animal": [A1, A2, A3],
            "several animals": [A1, A2, A3, B1, R1],
            "one session": [A1],
            "several sessions": [B1, A1],
            "animal + session": [B1, A1],
            "session + its own animal": [A1, A2, A3],
            "mixed, interleaved": [A1, A2, A3, B1, R1],
            "duplicates": [B1],
            "invalid + valid": [B1],
        },
        # remote, animal -> ephys sessions (ks)
        "remote_ephys": {
            "one animal": [A2, A3],
            "several animals": [A2, A3],
            "one session": [A1],
            "several sessions": [B1, A1],
            "animal + session": [A1],
            "session + its own animal": [A1, A2, A3],
            "mixed, interleaved": [A2, A3, B1],
            "duplicates": [B1],
            "invalid + valid": [B1],
        },
    }[config_kind][shape]


def _session_names(mock: MagicMock) -> list[str]:
    """First positional arg of every call, as a session name (paths -> folder name)."""
    return [getattr(c.args[0], "name", c.args[0]) for c in mock.call_args_list]


@pytest.fixture
def pipeline_stubs():
    """Replace the heavy pipeline modules (kilosort, nwb, pyaldata) with mocks."""
    stubs = {
        "bnd.pipeline.pyaldata": ModuleType("bnd.pipeline.pyaldata"),
        "bnd.pipeline.nwb": ModuleType("bnd.pipeline.nwb"),
        "bnd.pipeline.kilosort": ModuleType("bnd.pipeline.kilosort"),
    }
    stubs["bnd.pipeline.pyaldata"].run_pyaldata_conversion = MagicMock()
    stubs["bnd.pipeline.nwb"].run_nwb_conversion = MagicMock()
    stubs["bnd.pipeline.kilosort"].run_kilosort_on_session = MagicMock()
    stubs["bnd.pipeline.kilosort"].needs_kilosort = MagicMock(return_value=True)

    with patch.dict(sys.modules, stubs), patch("bnd.cli._check_processing_dependencies"):
        sys.modules.pop("bnd.pipeline.batch", None)
        yield {name.rsplit(".", 1)[1]: mod for name, mod in stubs.items()}


# ---------------------------- local, all sessions ----------------------------

LOCAL_COMMANDS = [
    ("to-pyal", "pyaldata", "run_pyaldata_conversion"),
    ("to-nwb", "nwb", "run_nwb_conversion"),
    ("ksort", "kilosort", "run_kilosort_on_session"),
]


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("command, module, func", LOCAL_COMMANDS, ids=[c[0] for c in LOCAL_COMMANDS])
def test_local_processing_commands(config, pipeline_stubs, command, module, func, shape):
    result = runner.invoke(app, [command, *SHAPES[shape]])
    assert result.exit_code == 0, result.output
    mock = getattr(pipeline_stubs[module], func)
    assert _session_names(mock) == _expected("local_all", shape)


def test_processing_passes_options(config, pipeline_stubs):
    result = runner.invoke(app, ["to-pyal", "M002", "-K", "-c"])
    assert result.exit_code == 0, result.output
    pipeline_stubs["pyaldata"].run_pyaldata_conversion.assert_called_once_with(
        config.get_local_session_path(B1), False, True
    )


# ---------------------------- up: last session ----------------------------


@pytest.mark.parametrize("shape", SHAPES)
def test_up(config, shape):
    with patch("bnd.cli.upload_session") as upload:
        result = runner.invoke(app, ["up", *SHAPES[shape]])
    assert result.exit_code == 0, result.output
    assert _session_names(upload) == _expected("local_last", shape)


# ---------------------------- dl / dl-light: remote ----------------------------


@pytest.mark.parametrize("shape", SHAPES)
def test_dl(config, shape):
    with patch("bnd.cli.download_session") as download:
        result = runner.invoke(app, ["dl", *SHAPES[shape]])
    assert result.exit_code == 0, result.output
    assert _session_names(download) == _expected("remote_all", shape)


@pytest.mark.parametrize("shape", SHAPES)
def test_dl_light(config, shape):
    with patch("bnd.cli.download_session_light") as download:
        result = runner.invoke(app, ["dl-light", *SHAPES[shape]])
    assert result.exit_code == 0, result.output
    assert _session_names(download) == _expected("remote_all", shape)


def test_dl_passes_options(config):
    with patch("bnd.cli.download_session") as download:
        result = runner.invoke(app, ["dl", "M002", A3, "-e", ".mat", "--max-size", "50", "-v"])
    assert result.exit_code == 0, result.output
    assert download.call_args_list == [
        ((B1, ".mat", 50.0, True),),
        ((A3, ".mat", 50.0, True),),
    ]


def test_dl_partial_session(config):
    with patch("bnd.cli.download_session") as download, patch("bnd.resolve.confirm", return_value=True):
        result = runner.invoke(app, ["dl", "M001_2024_03", "M002"])
    assert result.exit_code == 0, result.output
    assert _session_names(download) == [A3, B1]


def test_dl_remote_only_session(config):
    """`dl` looks sessions up remotely, so a session missing locally is fine."""
    with patch("bnd.cli.download_session") as download:
        result = runner.invoke(app, ["dl", A3])
    assert result.exit_code == 0, result.output
    assert _session_names(download) == [A3]


def test_up_remote_only_session_is_rejected(config):
    """`up` looks sessions up locally."""
    with patch("bnd.cli.upload_session") as upload:
        result = runner.invoke(app, ["up", A3])
    assert result.exit_code == 1
    upload.assert_not_called()


# ---------------------------- ks: remote ephys ----------------------------


@pytest.mark.parametrize("shape", SHAPES)
def test_ks(config, pipeline_stubs, shape):
    batch = importlib.import_module("bnd.pipeline.batch")
    with (
        patch.object(batch, "_load_config", return_value=config),
        patch.object(batch, "confirm", return_value=True),
        patch.object(batch, "download_session"),
        patch.object(batch, "download_session_light"),
        patch.object(batch, "upload_session") as upload,
        patch.object(batch.shutil, "rmtree"),
    ):
        result = runner.invoke(app, ["ks", *SHAPES[shape]])
    assert result.exit_code == 0, result.output
    assert _session_names(upload) == _expected("remote_ephys", shape)


def test_ks_skips_already_sorted(config, pipeline_stubs):
    pipeline_stubs["kilosort"].needs_kilosort.side_effect = lambda cfg, s: s != A2
    batch = importlib.import_module("bnd.pipeline.batch")
    with (
        patch.object(batch, "_load_config", return_value=config),
        patch.object(batch, "confirm", return_value=True),
        patch.object(batch, "download_session"),
        patch.object(batch, "download_session_light"),
        patch.object(batch, "upload_session") as upload,
        patch.object(batch.shutil, "rmtree"),
    ):
        result = runner.invoke(app, ["ks", "M001"])
    assert result.exit_code == 0, result.output
    assert _session_names(upload) == [A3]


# ---------------------------- all invalid -> exit 1 ----------------------------

INVALID = {
    "unknown animal": ["M009"],
    "unknown session": ["M001_2099_01_01_10_00"],
    "too short": ["abc"],
    "several invalid": ["M009", "abc", "M001_2099_01_01_10_00"],
}


@pytest.mark.parametrize("args", INVALID.values(), ids=INVALID.keys())
@pytest.mark.parametrize("command", ["to-pyal", "to-nwb", "ksort", "up", "dl", "dl-light", "ks"])
def test_all_invalid_exits(config, pipeline_stubs, command, args):
    batch = importlib.import_module("bnd.pipeline.batch")
    with (
        patch("bnd.cli.upload_session") as upload,
        patch("bnd.cli.download_session") as download,
        patch("bnd.cli.download_session_light") as download_light,
        patch.object(batch, "_load_config", return_value=config),
    ):
        result = runner.invoke(app, [command, *args])
    assert result.exit_code == 1, result.output
    for mock in (
        upload,
        download,
        download_light,
        pipeline_stubs["pyaldata"].run_pyaldata_conversion,
        pipeline_stubs["nwb"].run_nwb_conversion,
        pipeline_stubs["kilosort"].run_kilosort_on_session,
    ):
        mock.assert_not_called()


@pytest.mark.parametrize("command", ["to-pyal", "to-nwb", "ksort", "up", "dl", "dl-light", "ks", "ls"])
def test_invalid_targets_are_reported(config, pipeline_stubs, command):
    batch = importlib.import_module("bnd.pipeline.batch")
    with (
        patch("bnd.cli.upload_session"),
        patch("bnd.cli.download_session"),
        patch("bnd.cli.download_session_light"),
        patch.object(batch, "_load_config", return_value=config),
        patch.object(batch, "confirm", return_value=False),
        patch("subprocess.run"),
    ):
        result = runner.invoke(app, [command, "M009", "M001_2099_01_01_10_00", "M002"])
    assert "M009" in result.output
    assert "M001_2099_01_01_10_00" in result.output


@pytest.mark.parametrize("command", ["to-pyal", "to-nwb", "ksort", "up", "dl", "dl-light", "ks"])
def test_no_targets_is_a_usage_error(config, pipeline_stubs, command):
    result = runner.invoke(app, [command])
    assert result.exit_code == 2


# ---------------------------- ls ----------------------------

# (id, args, animals in the tree, sessions whose files are listed)
LS_CASES = [
    ("no targets: every animal", [], ["M001", "M002", "M003", "R001"], []),
    ("one animal", ["M001"], ["M001"], []),
    ("several animals", ["M002", "R001"], ["M002", "R001"], []),
    ("duplicate animals", ["M002", "M002"], ["M002"], []),
    ("animal without sessions", ["M003"], ["M003"], []),
    ("one session", [A1], [], [A1]),
    ("several sessions", [B1, A1], [], [B1, A1]),
    ("animal + session", ["M002", A1], ["M002"], [A1]),
    ("mixed, interleaved", ["M001", B1, "R001", A2], ["M001", "R001"], [B1, A2]),
    ("invalid animal + animal", ["M009", "M002"], ["M002"], []),
    ("invalid session + session", ["M001_2099_01_01_10_00", A1], [], [A1]),
    ("invalid session + animal", ["M001_2099_01_01_10_00", "M002"], ["M002"], []),
    ("invalid animal + session", ["M009", A1], [], [A1]),
]


@pytest.mark.parametrize(
    "args, animals, sessions", [c[1:] for c in LS_CASES], ids=[c[0] for c in LS_CASES]
)
def test_ls(config, args, animals, sessions):
    with patch("bnd.cli.print_session_tree") as tree, patch("bnd.cli.subprocess.run") as run:
        result = runner.invoke(app, ["ls", *args])
    assert result.exit_code == 0, result.output

    listed_dirs = [c.kwargs["cwd"].name for c in run.call_args_list]
    assert listed_dirs == sessions

    if animals:
        tree_data = tree.call_args.args[1]
        assert list(tree_data) == animals
    else:
        tree.assert_not_called()


def test_ls_tree_contents(config):
    with patch("bnd.cli.print_session_tree") as tree:
        result = runner.invoke(app, ["ls", "M001", "M003"])
    assert result.exit_code == 0, result.output
    assert tree.call_args.args[1] == {"M001": (2, [A1, A2]), "M003": (0, [])}


def test_ls_missing_flag(config):
    with patch("bnd.cli.print_session_tree") as tree:
        result = runner.invoke(app, ["ls", "M001", "-m"])
    assert result.exit_code == 0, result.output
    count, leaves = tree.call_args.args[1]["M001"]
    assert count == 2
    assert leaves[:2] == [A1, A2]
    assert len(leaves) == 3 and A3 in leaves[2]  # remote-only ephys session flagged


@pytest.mark.parametrize("args", [["M009"], ["M001_2099_01_01_10_00"], ["M009", "abc"]])
def test_ls_all_invalid_exits(config, args):
    with patch("bnd.cli.print_session_tree") as tree, patch("bnd.cli.subprocess.run") as run:
        result = runner.invoke(app, ["ls", *args])
    assert result.exit_code == 1, result.output
    tree.assert_not_called()
    run.assert_not_called()
