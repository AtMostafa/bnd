import platform
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich import print
from rich.tree import Tree

from .config import (
    _check_root,
    _check_session_directory,
    _get_env_path,
    _get_package_path,
    _load_config,
    get_last_session,
    list_dirs,
    list_session_datetime,
    missing_ephys_sessions,
)
from .data_transfer import download_session, download_session_light, upload_session
from .pipeline import _check_processing_dependencies
from .update_bnd import check_for_updates, update_bnd

# Create a Typer app
app = typer.Typer(
    add_completion=False,  # Disable the auto-completion options
)


# ============================== Pipeline functions =======================================


@app.command()
def to_pyal(
    session_name: str = typer.Argument(..., help="Session name to convert"),
    kilosort_flag: bool = typer.Option(
        True,
        "-k/-K",
        "--kilosort/--dont-kilosort",
        help="Run kilosort if available (-k) or dont (-K).",
    ),
    custom_map: bool = typer.Option(
        False,
        "-c/-C",
        "--custom-map/--default-map",
        help="Run conversion with a custom map (-c) or the not (-C)",
    ),
) -> None:
    """
    Convert session data into a pyaldata dataframe and saves it as a .mat

    \b
    If no .nwb file is present it will automatically generate one and if a nwb file is present it will skip it. If you want to generate a new one run `bnd to-nwb`

    \b
    If no kilosorted data is available it will not kilosort by default. If you want to kilosort add the flag `-k`

    \b
    Basic usage:
        `bnd to-pyal M037_2024_01_01_10_00  # Kilosorts data and converts to pyaldata
        `bnd to-pyal M037_2024_01_01_10_00 -c  # Uses custom mapping
    """
    _check_processing_dependencies()
    from .pipeline.pyaldata import run_pyaldata_conversion

    # Load config and get session path
    config = _load_config()
    session_path = config.get_local_session_path(session_name)

    # Check session directory
    _check_session_directory(session_path)

    # Run pipeline
    run_pyaldata_conversion(session_path, kilosort_flag, custom_map)



@app.command()
def to_nwb(
    session_name: str,
    kilosort_flag: bool = typer.Option(
        True,
        "-k/-K",
        "--kilosort/--dont-kilosort",
        help="Run kilosort if available (-k) or dont (-K).",
    ),
    custom_map: bool = typer.Option(
        False,
        "-c/-C",
        "--custom-map/--default-map",
        help="Run conversion with a custom map (-c) or the not (-C)",
    ),
) -> None:
    """
    Convert session data into a nwb file and saves it as a .nwb

    \b
    If no kilosorted data is available it will not kilosort by default. If you want to kilosort add the flag `-k`

    \b
    Basic usage:
        `bnd to-nwb M037_2024_01_01_10_00`
        `bnd to-nwb M037_2024_01_01_10_00 -c`  # Use custom channel mapping
    """
    # TODO: Add channel map argument: no-map, default-map, custom-map
    # _check_processing_dependencies()
    from .pipeline.nwb import run_nwb_conversion

    config = _load_config()
    session_path = config.get_local_session_path(session_name)

    # Check session directory
    _check_session_directory(session_path)

    # Run pipeline
    run_nwb_conversion(session_path, kilosort_flag, custom_map)


@app.command()
def ksort(session_name: str = typer.Argument(help="Session name to kilosort")) -> None:
    """
    Kilosorts data from a single session.

    \b
    Basic usage:
        `bnd ksort M037_2024_01_01_10_00`
    """
    # this will throw an error if the dependencies are not available
    _check_processing_dependencies()
    from .pipeline.kilosort import run_kilosort_on_session

    config = _load_config()
    session_path = config.get_local_session_path(session_name)

    # Check session directory
    _check_session_directory(session_path)

    # Run pipeline
    run_kilosort_on_session(session_path)


# ================================== Data Transfer ========================================


@app.command()
def up(
    session_or_animal_name: str = typer.Argument(
        help="Animal or session name: M123 or M123_2000_02_03_14_15"
    ),
):
    """
    Upload data to the server. If the file exists on the server, it won't be replaced.
    Every file in the session folder will get uploaded.
    If animal name give, the last session will get uploaded.

    \b
    Example usage to upload everything of a given session:
        `bnd up M017_2024_03_12_18_45`
    Upload everything of the last session:
        `bnd up M017`
    """
    if len(session_or_animal_name) > 4:  # session name
        upload_session(session_or_animal_name)
    elif len(session_or_animal_name) == 4:  # animal name
        config = _load_config()
        last_session = get_last_session(config.LOCAL_PATH / "raw" / session_or_animal_name)
        upload_session(last_session)
    else:
        print("[red]Input must be either a session or an animal name.")
        raise typer.Exit(code=1)


@app.command()
def dl(
    session_name: str = typer.Argument(help="Name of session: M123_2000_02_03_14_15"),
    file_extension: Annotated[str, typer.Argument(help="One file type to download")] = ".*",
    max_size_MB: float = typer.Option(
        0,
        "--max-size",
        help="Maximum size in MB. Any smaller file will be downloaded. Zero mean infinite size.",
    ),
    do_video: bool = typer.Option(
        False,
        "--video/--no-video",
        "-v/-V",
        help="Download video files as well, if they are smaller than `--max-size`. No video files by default.",
    ),
):
    """
    Download data of a given session from the remote server.
    If session exists locally, only missing files will be downloaded.
    if session name is not complete (`M123_2025_02_03`), it will try to find a similar session.

    \b
    Example usage to download everything:
        `bnd dl M017_2024_03_12_18_45 -v` will download everything, including videos
        `bnd dl M017_2024_03_12_18_45` will download everything, except videos
        `bnd dl M017_2024_03_12_18_45 --max-size=50` will download files smaller than 50MB
        `bnd dl M056_2025_03_01 .mat` will download all the '.mat' files from the matching session
    """
    download_session(session_name, file_extension, max_size_MB, do_video)


@app.command()
def dl_light(
    session_name: str = typer.Argument(help="Name of session: M123_2000_02_03_14_15"),
    max_size_MB: float = typer.Option(
        0,
        "--max-size",
        help="Maximum size in MB. Any smaller file will be downloaded. Zero mean infinite size.",
    ),
):
    """
    Download a session, skipping bulky raw data.
    Like `dl` but always skips: video files, SpikeGLX data files (`..._g?_...`) except their `*.meta`
    files, anything inside a `..._ksort` folder, and anything inside a `..._camera`/`..._cameras` folder.
    If session exists locally, only missing files will be downloaded.

    \b
    Example usage:
        `bnd dl-light M017_2024_03_12_18_45` downloads everything except the bulky raw data
        `bnd dl-light M056_2025_03_01 .mat` downloads all the '.mat' files from the matching session
    """
    download_session_light(session_name, max_size_MB)


# =================================== Listing ==========================================


@app.command()
def ls(
    animal_name: str = typer.Argument(
        None,
        help="Animal name (M123) or session name (M123_2000_02_03_14_15). If omitted, lists every animal.",
    ),
    missing: bool = typer.Option(
        False,
        "-m",
        "--missing",
        help="Also show Ephys sessions missing locally.",
    ),
):
    """
    List the sessions available locally.
    If a session name is given instead, show its contents.

    \b
    Example usage:
        `bnd ls` lists every animal and its sessions
        `bnd ls M170` lists the sessions of M017 only
        `bnd ls M170_2024_03_12_18_45` shows that session's files
        `bnd ls -m` also flags remote ephys sessions missing locally
        `bnd ls M170 -m` same, for M017 only
    """
    config = _load_config()
    raw_path = config.LOCAL_PATH / "raw"

    if animal_name is not None and len(animal_name) > 4:  # session name
        session_path = config.get_local_session_path(animal_name)
        if not session_path.is_dir():
            print(f"[red]Session {animal_name} not found in {raw_path}")
            raise typer.Exit(code=1)
        
        print(f"[green]Session path: {session_path}")
        if platform.system() == "Windows":
            subprocess.run(r"dir /b", shell=True, cwd=session_path, check=False)
        else:
            subprocess.run(r"du -sh *", shell=True, cwd=session_path, check=False)
        return

    if animal_name is not None:
        animal_path = config.get_local_animal_path(animal_name)
        if not animal_path.is_dir():
            print(f"[red]Animal {animal_name} not found in {raw_path}")
            raise typer.Exit(code=1)
        animal_names = [animal_path.name]
    else:
        animal_names = sorted(list_dirs(raw_path))
        if not animal_names:
            print(f"[yellow]No animals found in {raw_path}")
            return

    tree = Tree(f"[bold]{raw_path}")
    for animal in animal_names:
        _, sessions = list_session_datetime(raw_path / animal)
        absent = missing_ephys_sessions(animal, sessions) if missing else []
        branch = tree.add(f"[bold cyan]{animal}[/] [dim]({len(sessions)})")
        for session in sessions:
            branch.add(session)
        for session in absent:
            branch.add(f"[yellow]{session}[/] [dim](remote-only)")
        if not sessions and not absent:
            branch.add("[dim]no sessions")

    print(tree)


# =================================== Batch ==========================================


@app.command()
def ks(
    targets: Annotated[
        list[str],
        typer.Argument(
            help="Animal names (M123) and/or session names (M123_2000_02_03_14_15) to kilosort."
        ),
    ],
):
    """
    Kilosort every not-yet-processed sessions of the given animals/sessions.

    \b
    A session is skipped if it already has a `_ksort` folder or a pyaldata/nwb file.
    For every remaining session: download (no video), convert to pyaldata,
    upload back to the server, then replace the bulky local raw data with
    a light copy (like `dl-light`).

    \b
    Example usage:
        `yes | bnd ks M123 M124` kilosorts all pending sessions of M123 and M124
        `yes | bnd ks M123_2000_02_03_14_15 M123_2024_01_01_10_00` kilosorts just that session
    """
    _check_processing_dependencies()
    from .pipeline.kilosort import needs_kilosort

    config = _load_config()

    session_names: list[str] = []
    errors: list[tuple[str, str]] = []

    for target in targets:
        if len(target) > 4:  # session name
            session_names.append(target)
        elif len(target) == 4:  # animal name
            remote_animal_path = config.get_remote_animal_path(target)
            if not remote_animal_path.is_dir():
                errors.append((target, "animal not found on remote"))
                continue
            _, sessions = list_session_datetime(remote_animal_path)
            session_names.extend(sessions)
        else:
            errors.append((target, "not a valid animal or session name"))

    pending_sessions = [s for s in session_names if needs_kilosort(config, s)]

    if not pending_sessions:
        print("[yellow]No sessions need kilosorting.")
    else:
        print(f"[green]Found {len(pending_sessions)} session(s) to kilosort:")
        for session in pending_sessions:
            print(f"  - {session}")

        for session in pending_sessions:
            animal = session[:4]
            local_session_path = config.LOCAL_PATH / "raw" / animal / session
            print(f"\n[bold cyan]Processing {session}[/]")
            try:
                dl(session, max_size_MB=0, do_video=False)
                to_pyal(session, kilosort_flag=True, custom_map=True)
                up(session)
                shutil.rmtree(local_session_path, ignore_errors=True)
                dl_light(session)
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


# =================================== Updating ==========================================


@app.command()
def check_updates():
    """
    Check if there are any new commits on the repo's main branch.
    """
    check_for_updates()


@app.command()
def self_update():
    """
    Update the bnd tool by pulling the latest commits from the repo's main branch.
    """
    update_bnd()


# =================================== Config ============================================


@app.command()
def show_config():
    """
    Show the contents of the config file.
    """
    config = _load_config()
    print(f"bnd source code is at {_get_package_path()}", end="\n\n")
    for attr, value in config.__dict__.items():
        print(f"{attr}: {value}")


@app.command()
def check_config():
    """
    Check that the local and remote root folders have the expected raw and processed folders.
    """
    config = _load_config()

    print(
        "Checking that local and remote root folders have the expected raw and processed folders..."
    )

    _check_root(config.LOCAL_PATH)
    _check_root(config.REMOTE_PATH)

    print("[green]Config looks good.")


@app.command()
def init():
    """
    Create a .env file to store the paths to the local and remote data storage.
    """

    # check if the file exists
    env_path = _get_env_path()

    if env_path.exists():
        print("\n[yellow]Config file already exists.\n")

        check_config()

    else:
        print("\nConfig file doesn't exist. Let's create one.")

        local_path = Path(
            typer.prompt("Enter the absolute path to the root of the local data storage")
        )
        _check_root(local_path)

        remote_path = Path(
            typer.prompt("Enter the absolute path to the root of remote data storage")
        )
        _check_root(remote_path)

        with open(env_path, "w") as f:
            f.write(f"LOCAL_PATH = {local_path}\n")
            f.write(f"REMOTE_PATH = {remote_path}\n")

        # make sure that it works
        check_config()

        print("[green]Config file created successfully.")


# Main Entry Point
if __name__ == "__main__":
    app()
