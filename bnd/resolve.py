"""Central resolution of user-given targets (animals and/or sessions) into session names.

Every command that accepts "an animal, a session, or a list of them" should call
`resolve_sessions` instead of parsing the input itself.

A 4-character target is an animal name (`M123`); a longer one is a session name
(`M123_2000_02_03_14_15`), whose animal is its first 4 characters.
"""

from collections.abc import Callable

import typer
from rich import print

from .config import Config, _load_config, list_session_datetime
from .display import confirm

SessionPicker = Callable[[list[str]], list[str]]


def is_animal(target: str) -> bool:
    """A target is an animal name if it is exactly 4 characters long (`M123`)."""
    return len(target) == 4


def _raw_root(config: Config, remote: bool):
    return (config.REMOTE_PATH if remote else config.LOCAL_PATH) / "raw"


def _animal_sessions(config: Config, remote: bool, animal: str) -> list[str] | None:
    """Sessions of `animal` sorted by date, or None if the animal folder doesn't exist."""
    animal_path = _raw_root(config, remote) / animal
    if not animal_path.is_dir():
        return None
    return list_session_datetime(animal_path, config.datetime_pattern)[1]


# ------------------------------- pickers -------------------------------------
# A picker narrows down the sessions an *animal* name expands to.
# Explicitly named sessions are never filtered.


def last_session(sessions: list[str]) -> list[str]:
    """Keep only the most recent session."""
    return sessions[-1:]


def ephys_sessions(config: Config, remote: bool) -> SessionPicker:
    """Keep only sessions that have a SpikeGLX gate folder (`*_g?`)."""
    root = _raw_root(config, remote)

    def pick(sessions: list[str]) -> list[str]:
        return [
            s
            for s in sessions
            if config.get_subdirectories_from_pattern(root / config.get_animal_name(s) / s, "*_g?")
        ]

    return pick


# ------------------------------- resolver ------------------------------------


def _match_session(config: Config, remote: bool, target: str, fuzzy: bool) -> str | None:
    """Full session name for `target`, or None if there is no (accepted) match."""
    sessions = _animal_sessions(config, remote, config.get_animal_name(target)) or []
    if target in sessions:
        return target
    if not fuzzy:
        return None

    matches = [s for s in sessions if target in s]
    if matches and confirm(f"\n{target} not found. Did you mean {matches[0]} (y/n)? "):
        return matches[0]
    return None


def resolve_sessions(
    targets: str | list[str],
    *,
    remote: bool = False,
    pick: SessionPicker | None = None,
    fuzzy: bool = False,
    config: Config | None = None,
) -> list[str]:
    """
    Resolve animal and/or session names into an ordered, de-duplicated list of session names.

    targets: one name or a list of names, each an animal (`M123`) or a session (`M123_2000_02_03_14_15`).
    remote: look sessions up on the remote server instead of locally.
    pick: narrows the sessions an animal expands to (e.g. `last_session`). Default: all of them.
    fuzzy: allow a partial session name (`M123_2000_02_03`): the first session containing it
        is offered, and used only if the user confirms.

    Invalid targets (unknown animal or session, name shorter than 4 characters, declined match)
    are reported and skipped. An animal with no matching sessions is reported but is not an error.
    Exits with code 1 if every target is invalid. An empty `targets` returns an empty list.
    """
    if config is None:
        config = _load_config()
    if isinstance(targets, str):
        targets = [targets]

    root = _raw_root(config, remote)
    resolved: list[str] = []
    n_errors = 0

    for target in targets:
        if is_animal(target):
            sessions = _animal_sessions(config, remote, target)
            if sessions is None:
                print(f"[red]{target}: animal not found in {root}. Skipping.")
                n_errors += 1
                continue
            if pick is not None:
                sessions = pick(sessions)
            if not sessions:
                print(f"[yellow]{target}: no matching sessions.")
            resolved.extend(sessions)
        elif len(target) > 4:
            match = _match_session(config, remote, target, fuzzy)
            if match is None:
                print(f"[red]{target}: session not found in {root}. Skipping.")
                n_errors += 1
                continue
            resolved.append(match)
        else:
            print(f"[red]{target}: not a valid animal (M123) or session (M123_2000_02_03_14_15) name. Skipping.")
            n_errors += 1

    if targets and n_errors == len(targets):
        raise typer.Exit(code=1)

    return list(dict.fromkeys(resolved))
