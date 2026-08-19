"""Batch-processing pipelines spanning multiple sessions."""

import shutil

import typer
from rich import print

from ..config import _load_config, missing_ephys_sessions
from ..data_transfer import download_session, download_session_light, upload_session
from ..display import confirm, print_session_tree
from .kilosort import needs_kilosort
from .pyaldata import run_pyaldata_conversion


def run_kilosort_batch(targets: list[str]) -> None:
    """
    Kilosort every not-yet-processed sessions of the given animals/sessions.
    If animal name is given, only ephys sessions will be included.

    \b
    A session is skipped if it already has a `_ksort` folder or a pyaldata/nwb file.
    For every remaining session: download (no video), convert to pyaldata,
    upload back to the server, then replace the bulky local raw data with
    a light copy (like `dl-light`).
    """
    config = _load_config()

    session_names: list[str] = []
    errors: list[tuple[str, str]] = []

    for target in targets:
        if len(target) > 4:  # session name
            session_names.append(target)
        elif len(target) == 4:  # animal name
            sessions = missing_ephys_sessions(target, [])
            session_names.extend(sessions)
        else:
            errors.append((target, "not a valid animal or session name"))

    pending_sessions = [s for s in session_names if needs_kilosort(config, s)]

    if not pending_sessions:
        print("[yellow]No sessions need kilosorting.")
    else:
        sessions_by_animal: dict[str, list[str]] = {}
        for session in pending_sessions:
            sessions_by_animal.setdefault(session[:4], []).append(session)

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
            animal = session[:4]
            local_session_path = config.LOCAL_PATH / "raw" / animal / session
            print(f"\n[bold cyan]Processing {session}[/]")
            try:
                download_session(session, ".*", max_size_MB=0, do_video=False)
                session_path = config.get_local_session_path(session)
                run_pyaldata_conversion(session_path, kilosort_flag=True, custom_map=True)
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
