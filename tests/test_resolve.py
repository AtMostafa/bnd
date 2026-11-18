"""Every input shape `resolve_sessions` can receive: animals, sessions, and combinations."""

from unittest.mock import patch

import pytest
import typer

from bnd.resolve import ephys_sessions, is_animal, last_session, resolve_sessions

from .conftest import A1, A2, A3, B1, R1

LAST = "last"
EPHYS = "ephys"


def _resolve(config, targets, remote=False, pick=None, fuzzy=False):
    if pick == LAST:
        pick = last_session
    elif pick == EPHYS:
        pick = ephys_sessions(config, remote)
    return resolve_sessions(targets, remote=remote, pick=pick, fuzzy=fuzzy, config=config)


# (id, targets, kwargs, expected)
CASES = [
    # ---------------- animals only ----------------
    ("one animal as str", "M001", {}, [A1, A2]),
    ("one animal in list", ["M001"], {}, [A1, A2]),
    ("several animals", ["M001", "M002", "R001"], {}, [A1, A2, B1, R1]),
    ("animal order is kept", ["R001", "M001"], {}, [R1, A1, A2]),
    ("duplicate animals", ["M001", "M001"], {}, [A1, A2]),
    ("non-M animal", "R001", {}, [R1]),
    ("animal without sessions", "M003", {}, []),
    ("animal without sessions + animal", ["M003", "M002"], {}, [B1]),
    # ---------------- sessions only ----------------
    ("one session as str", A1, {}, [A1]),
    ("one session in list", [A1], {}, [A1]),
    ("several sessions, same animal", [A2, A1], {}, [A2, A1]),
    ("several sessions, different animals", [B1, A1, R1], {}, [B1, A1, R1]),
    ("duplicate sessions", [A1, A1], {}, [A1]),
    # ---------------- animals + sessions ----------------
    ("animal + session of another animal", ["M002", A1], {}, [B1, A1]),
    ("session + its own animal", [A1, "M001"], {}, [A1, A2]),
    ("animal + one of its own sessions", ["M001", A1], {}, [A1, A2]),
    ("several of each, interleaved", ["M001", B1, "R001", A2], {}, [A1, A2, B1, R1]),
    # ---------------- empty ----------------
    ("empty list", [], {}, []),
    # ---------------- pick=last_session (`up`) ----------------
    ("last: one animal", "M001", {"pick": LAST}, [A2]),
    ("last: several animals", ["M001", "M002", "R001"], {"pick": LAST}, [A2, B1, R1]),
    ("last: explicit session not filtered", A1, {"pick": LAST}, [A1]),
    ("last: several explicit sessions", [A1, B1], {"pick": LAST}, [A1, B1]),
    ("last: animal + older session", ["M001", A1], {"pick": LAST}, [A2, A1]),
    ("last: animal without sessions", "M003", {"pick": LAST}, []),
    # ---------------- remote (`dl`, `dl-light`) ----------------
    ("remote: one animal", "M001", {"remote": True}, [A1, A2, A3]),
    ("remote: several animals", ["M001", "M002"], {"remote": True}, [A1, A2, A3, B1]),
    ("remote: remote-only session", A3, {"remote": True}, [A3]),
    ("remote: sessions", [A3, B1], {"remote": True}, [A3, B1]),
    ("remote: animal + session", ["R001", A3], {"remote": True}, [R1, A3]),
    # ---------------- remote + ephys (`ks`) ----------------
    ("ephys: one animal", "M001", {"remote": True, "pick": EPHYS}, [A2, A3]),
    ("ephys: animal without ephys", "M002", {"remote": True, "pick": EPHYS}, []),
    ("ephys: several animals", ["M001", "M002", "R001"], {"remote": True, "pick": EPHYS}, [A2, A3]),
    ("ephys: explicit non-ephys session kept", A1, {"remote": True, "pick": EPHYS}, [A1]),
    ("ephys: sessions", [B1, A3], {"remote": True, "pick": EPHYS}, [B1, A3]),
    ("ephys: session + animal", [A1, "M001"], {"remote": True, "pick": EPHYS}, [A1, A2, A3]),
    # ---------------- some invalid targets are skipped ----------------
    ("unknown animal + animal", ["M009", "M001"], {}, [A1, A2]),
    ("4-char non-animal + session", ["abcd", A1], {}, [A1]),
    ("too short + session", ["abc", B1], {}, [B1]),
    ("unknown session + animal", ["M001_2099_01_01_10_00", "M002"], {}, [B1]),
    ("session of unknown animal + session", ["M009_2024_01_01_10_00", A1], {}, [A1]),
    ("remote-only session looked up locally + session", [A3, A1], {}, [A1]),
    ("partial session without fuzzy + animal", ["M001_2024_02", "M002"], {}, [B1]),
    ("empty string + animal", ["", "M002"], {}, [B1]),
]


@pytest.mark.parametrize(
    "targets, kwargs, expected", [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_resolve(config, targets, kwargs, expected):
    assert _resolve(config, targets, **kwargs) == expected


# (id, targets, kwargs)
EXIT_CASES = [
    ("unknown animal", "M009", {}),
    ("unknown session", "M001_2099_01_01_10_00", {}),
    ("too short", "abc", {}),
    ("empty string", "", {}),
    ("remote-only session looked up locally", A3, {}),
    ("all invalid, mixed", ["M009", "abc", "M001_2099_01_01_10_00"], {}),
    ("partial session without fuzzy", "M001_2024_02", {}),
    ("remote: animal only local", "M003", {"remote": True}),
]


@pytest.mark.parametrize(
    "targets, kwargs", [c[1:] for c in EXIT_CASES], ids=[c[0] for c in EXIT_CASES]
)
def test_all_invalid_exits(config, targets, kwargs):
    with pytest.raises(typer.Exit) as exc:
        _resolve(config, targets, **kwargs)
    assert exc.value.exit_code == 1


def test_invalid_targets_are_reported(config, capsys):
    _resolve(config, ["M009", "abc", "M001_2099_01_01_10_00", "M002"])
    out = capsys.readouterr().out
    for name in ("M009", "abc", "M001_2099_01_01_10_00"):
        assert name in out


def test_animal_without_sessions_is_reported(config, capsys):
    _resolve(config, "M003")
    assert "M003" in capsys.readouterr().out


# ---------------- fuzzy (partial session names) ----------------

# (id, targets, remote, expected)
FUZZY_CASES = [
    ("partial session", "M001_2024_02", False, [A2]),
    ("ambiguous partial -> first match", "M001_2024", False, [A1]),
    ("partial + animal", ["M002", "M001_2024_02"], False, [B1, A2]),
    ("partial + full session", [A1, "M002_2024_01"], False, [A1, B1]),
    ("partial resolving to an explicit one", [A2, "M001_2024_02"], False, [A2]),
    ("remote partial", "M001_2024_03", True, [A3]),
    ("full name needs no confirmation", A1, False, [A1]),
]


@pytest.mark.parametrize(
    "targets, remote, expected", [c[1:] for c in FUZZY_CASES], ids=[c[0] for c in FUZZY_CASES]
)
def test_fuzzy_confirmed(config, targets, remote, expected):
    with patch("bnd.resolve.confirm", return_value=True):
        assert _resolve(config, targets, remote=remote, fuzzy=True) == expected


def test_fuzzy_full_name_does_not_prompt(config):
    with patch("bnd.resolve.confirm") as confirm:
        _resolve(config, [A1, "M002"], fuzzy=True)
    confirm.assert_not_called()


def test_fuzzy_declined_is_skipped(config):
    with patch("bnd.resolve.confirm", return_value=False):
        assert _resolve(config, ["M001_2024_02", "M002"], fuzzy=True) == [B1]
        with pytest.raises(typer.Exit):
            _resolve(config, "M001_2024_02", fuzzy=True)


def test_fuzzy_no_match(config):
    with patch("bnd.resolve.confirm") as confirm, pytest.raises(typer.Exit):
        _resolve(config, "M001_2099", fuzzy=True)
    confirm.assert_not_called()


# ---------------- helpers ----------------


@pytest.mark.parametrize(
    "target, expected",
    [("M001", True), ("R001", True), ("abcd", True), ("abc", False), ("", False), (A1, False)],
)
def test_is_animal(target, expected):
    assert is_animal(target) is expected


def test_config_loaded_when_not_given(config):
    assert resolve_sessions("M002") == [B1]


def test_supplied_config_is_used_without_env_file(config):
    """With an explicit config, no global config (~/.bnd/.env) is loaded."""
    no_env = typer.Exit(code=1)
    with (
        patch("bnd.config._load_config", side_effect=no_env),
        patch("bnd.resolve._load_config", side_effect=no_env),
    ):
        assert resolve_sessions(["M001", B1], config=config) == [A1, A2, B1]
        assert resolve_sessions("M001", remote=True, pick=ephys_sessions(config, True), config=config) == [A2, A3]
        with patch("bnd.resolve.confirm", return_value=True):
            assert resolve_sessions("M001_2024_02", fuzzy=True, config=config) == [A2]
