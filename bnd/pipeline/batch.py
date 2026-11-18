"""Batch-processing pipelines spanning multiple sessions."""

import shutil

import typer
from rich import print

from ..config import _load_config
from ..data_transfer import download_session, download_session_light, upload_session
from ..display import confirm, print_session_tree
from ..resolve import ephys_sessions, resolve_sessions
from .kilosort import needs_kilosort
from .pyaldata import run_pyaldata_conversion


def run_kilosort_batch(targets: list[str]) -> None:
    """
    Kilosort every not-yet-processed session of the given animals/sessions.
    An animal name expands to its ephys sessions (with a `_g?` gate folder) on the server.
    Session names given explicitly are always included. Invalid targets are reported and skipped.

    A session is skipped if it already has a `_ksort` folder or a pyaldata/nwb file on the server.
    For every remaining session: download (no video), convert to pyaldata,
    upload back to the server, then replace the bulky local raw data with
    a light copy (like `dl-light`).
    """
    config = _load_config()

    errors: list[tuple[str, str]] = []

    session_names = resolve_sessions(
        targets, remote=True, pick=ephys_sessions(config, remote=True), config=config
    )

    pending_sessions = [s for s in session_names if needs_kilosort(config, s)]

    if not pending_sessions:
        print("[yellow]No sessions need kilosorting.")
    else:
        sessions_by_animal: dict[str, list[str]] = {}
        for session in pending_sessions:
            sessions_by_animal.setdefault(config.get_animal_name(session), []).append(session)

        animals_tree_data = {
            animal: (len(sessions), sessions) for animal, sessions in sessions_by_animal.items()
        }
        print_session_tree(
            f"[bold green]{len(pending_sessions)} session(s) pending kilosort", animals_tree_data
        )

        if not confirm("\nProceed with kilosorting these sessions (y/n)? "):
            print("[yellow]Aborted.")
            raise typer.Exit(code=0)

        for session in pending_sessions:
            local_session_path = config.get_local_session_path(session)
            print(f"\n[bold cyan]Processing {session}[/]")
            try:
                download_session(session, ".*", max_size_MB=0, do_video=False)
                run_pyaldata_conversion(local_session_path, kilosort_flag=True, custom_map=True)
                upload_session(session)
                shutil.rmtree(local_session_path, ignore_errors=True)
                download_session_light(session, max_size_MB=0)
            except Exception as e:
                print(f"[red]Error processing {session}: {e}")
                errors.append((session, str(e)))
                shutil.rmtree(local_session_path, ignore_errors=True)
                continue

    print("\n[bold]Done.[/]")
    if errors:
        print(f"[red]{len(errors)} issue(s):")
        for name, reason in errors:
            print(f"  - {name}: {reason}")
    else:
        print("[green]All sessions processed successfully.")
