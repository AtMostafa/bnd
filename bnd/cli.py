import platform
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print

from .config import (
    _check_root,
    _check_session_directory,
    _get_env_path,
    _get_package_path,
    _load_config,
    check_config,
    get_repo_url,
    get_version,
    list_dirs,
    list_session_datetime,
    missing_ephys_sessions,
)
from .data_transfer import download_session, download_session_light, upload_session
from .display import print_session_tree
from .pipeline import _check_processing_dependencies
from .resolve import is_animal, last_session, resolve_sessions

# Create a Typer app
app = typer.Typer(
    add_completion=False,  # Disable the auto-completion options
)


def _version_callback(show_version: bool) -> None:
    if show_version:
        repo_url = get_repo_url()
        if repo_url:
            print(f"[link={repo_url}]{repo_url}")
        print(f"bnd {get_version()}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show the bnd version and exit.",
    ),
) -> None:
    pass


# ============================== Pipeline functions =======================================


@app.command()
def to_pyal(
    targets: Annotated[
        list[str],
        typer.Argument(help="Animal and/or session names to process. An animal means all its local sessions."),
    ],
    kilosort_flag: bool = typer.Option(
        True,
        "-k/-K",
        "--kilosort/--dont-kilosort",
        help="Kilosort the session first (-k, default) or don't (-K). Skipped if a `_ksort` folder already exists.",
    ),
    custom_map: bool = typer.Option(
        False,
        "-c/-C",
        "--custom-map/--default-map",
        help="Use the custom channel map `custom_map.json` (-c) or the default map (-C, default).",
    ),
) -> None:
    """
    Convert sessions into pyaldata dataframes, saved as .mat files.
    An animal name converts all its local sessions.

    \b
    If a session has no .nwb file, one is generated first; an existing .nwb file is reused.
    To regenerate it, run `bnd to-nwb`.

    \b
    Sessions are kilosorted first by default (unless a `_ksort` folder already exists). Use `-K` to skip kilosort.

    \b
    Basic usage:
        `bnd to-pyal M037_2024_01_01_10_00`  # Kilosorts data and converts to pyaldata
        `bnd to-pyal M037_2024_01_01_10_00 -K`  # Converts without kilosorting
        `bnd to-pyal M037_2024_01_01_10_00 -c`  # Uses custom mapping
        `bnd to-pyal M037 M038_2024_01_01_10_00`  # Every local session of M037, plus one session of M038
    """
    _check_processing_dependencies()
    from .pipeline.pyaldata import run_pyaldata_conversion

    config = _load_config()
    for session_name in resolve_sessions(targets, config=config):
        session_path = config.get_local_session_path(session_name)
        _check_session_directory(session_path)
        run_pyaldata_conversion(session_path, kilosort_flag, custom_map)



@app.command()
def to_nwb(
    targets: Annotated[
        list[str],
        typer.Argument(help="Animal and/or session names to process. An animal means all its local sessions."),
    ],
    kilosort_flag: bool = typer.Option(
        True,
        "-k/-K",
        "--kilosort/--dont-kilosort",
        help="Kilosort the session first (-k, default) or don't (-K). Skipped if a `_ksort` folder already exists.",
    ),
    custom_map: bool = typer.Option(
        False,
        "-c/-C",
        "--custom-map/--default-map",
        help="Use the custom channel map `custom_map.json` (-c) or the default map (-C, default).",
    ),
) -> None:
    """
    Convert sessions into .nwb files.
    An animal name converts all its local sessions. If a .nwb file already exists, you are asked before it is overwritten.

    \b
    Sessions are kilosorted first by default (unless a `_ksort` folder already exists). Use `-K` to skip kilosort.

    \b
    Basic usage:
        `bnd to-nwb M037_2024_01_01_10_00`
        `bnd to-nwb M037_2024_01_01_10_00 -K`  # Converts without kilosorting
        `bnd to-nwb M037_2024_01_01_10_00 -c`  # Use custom channel mapping
        `bnd to-nwb M037`  # Every local session of M037
    """
    # TODO: Add channel map argument: no-map, default-map, custom-map
    # _check_processing_dependencies()
    from .pipeline.nwb import run_nwb_conversion

    config = _load_config()
    for session_name in resolve_sessions(targets, config=config):
        session_path = config.get_local_session_path(session_name)
        _check_session_directory(session_path)
        run_nwb_conversion(session_path, kilosort_flag, custom_map)


@app.command()
def ksort(
    targets: Annotated[
        list[str],
        typer.Argument(help="Animal and/or session names to process. An animal means all its local sessions."),
    ],
) -> None:
    """
    Kilosort the given sessions on all available probes and recordings.
    An animal name kilosorts all its local sessions. Sessions that already have a `_ksort` folder are skipped.

    \b
    Basic usage:
        `bnd ksort M037_2024_01_01_10_00`
        `bnd ksort M037 M038`  # Every local session of M037 and M038
    """
    # this will throw an error if the dependencies are not available
    _check_processing_dependencies()
    from .pipeline.kilosort import run_kilosort_on_session

    config = _load_config()
    for session_name in resolve_sessions(targets, config=config):
        session_path = config.get_local_session_path(session_name)
        _check_session_directory(session_path)
        run_kilosort_on_session(session_path)


# ================================== Data Transfer ========================================


@app.command()
def up(
    targets: Annotated[
        list[str],
        typer.Argument(help="Animal and/or session names: M123 or M123_2000_02_03_14_15"),
    ],
):
    """
    Upload sessions to the server. Files that already exist on the server are not replaced.
    Every file in the session folder will get uploaded.
    An animal name uploads its last local session.

    \b
    Example usage:
        `bnd up M017_2024_03_12_18_45`  # Upload everything of that session
        `bnd up M017`  # Upload the last session of M017
        `bnd up M017 M018`  # Upload the last session of each animal
    """
    for session_name in resolve_sessions(targets, pick=last_session):
        upload_session(session_name)


@app.command()
def dl(
    targets: Annotated[
        list[str],
        typer.Argument(help="Animal and/or session names: M123 or M123_2000_02_03_14_15"),
    ],
    file_extension: str = typer.Option(
        ".*", "--ext", "-e", help="One file type to download, e.g. `.mat`."
    ),
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
    Download sessions from the remote server.
    An animal name downloads all its remote sessions.
    If a session exists locally, only missing files are downloaded.
    If a session name is incomplete (`M123_2025_02_03`), the first matching session is offered for confirmation.

    \b
    Example usage:
        `bnd dl M017_2024_03_12_18_45 -v` will download everything, including videos
        `bnd dl M017_2024_03_12_18_45` will download everything, except videos
        `bnd dl M017_2024_03_12_18_45 --max-size=50` will download files smaller than 50MB
        `bnd dl M056_2025_03_01 -e .mat` will download all the '.mat' files from the matching session
        `bnd dl M017 M018` will download every session of both animals, except videos
    """
    for session_name in resolve_sessions(targets, remote=True, fuzzy=True):
        download_session(session_name, file_extension, max_size_MB, do_video)


@app.command()
def dl_light(
    targets: Annotated[
        list[str],
        typer.Argument(help="Animal and/or session names: M123 or M123_2000_02_03_14_15"),
    ],
    max_size_MB: float = typer.Option(
        0,
        "--max-size",
        help="Maximum size in MB. Any smaller file will be downloaded. Zero mean infinite size.",
    ),
):
    """
    Download sessions, skipping bulky raw data.
    An animal name downloads all its remote sessions.
    Like `dl` but always skips: video files, SpikeGLX data files (`..._g?_...`) except their `*.meta`
    files, anything inside a `..._ksort` folder, and anything inside a `..._camera`/`..._cameras` folder.
    If a session exists locally, only missing files are downloaded.
    Incomplete session names are matched like in `dl`.

    \b
    Example usage:
        `bnd dl-light M017_2024_03_12_18_45` downloads everything except the bulky raw data
        `bnd dl-light M017` downloads every session of M017
    """
    for session_name in resolve_sessions(targets, remote=True, fuzzy=True):
        download_session_light(session_name, max_size_MB)


# =================================== Listing ==========================================


@app.command()
def ls(
    targets: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Animal names (M123) and/or session names (M123_2000_02_03_14_15). If omitted, lists every animal.",
        ),
    ] = None,
    missing: bool = typer.Option(
        False,
        "-m",
        "--missing",
        help="Also show Ephys sessions missing locally.",
    ),
):
    """
    List the sessions available locally, for the given animals or for every animal.
    For each session name given, show that session's files. Animals and sessions can be mixed.

    \b
    Example usage:
        `bnd ls` lists every animal and its sessions
        `bnd ls M170` lists the sessions of M170 only
        `bnd ls M170 M171` lists the sessions of both animals
        `bnd ls M170_2024_03_12_18_45` shows that session's files
        `bnd ls -m` also flags remote ephys sessions missing locally
        `bnd ls M170 -m` same, for M170 only
    """
    config = _load_config()
    raw_path = config.LOCAL_PATH / "raw"

    if targets:
        animal_names = []
        for animal in dict.fromkeys(t for t in targets if is_animal(t)):
            if (raw_path / animal).is_dir():
                animal_names.append(animal)
            else:
                print(f"[red]{animal}: animal not found in {raw_path}. Skipping.")
        session_targets = [t for t in targets if not is_animal(t)]
        session_names = []
        if session_targets:
            try:
                session_names = resolve_sessions(session_targets, config=config)
            except typer.Exit:
                if not animal_names:
                    raise
        if not animal_names and not session_names:
            raise typer.Exit(code=1)
    else:
        session_names = []
        animal_names = sorted(list_dirs(raw_path))
        if not animal_names:
            print(f"[yellow]No animals found in {raw_path}")
            return

    for session_name in session_names:
        session_path = config.get_local_session_path(session_name)
        print(f"[green]Session path: {session_path}")
        if platform.system() == "Windows":
            subprocess.run(r"dir /b", shell=True, cwd=session_path, check=False)
        else:
            subprocess.run(r"du -sh *", shell=True, cwd=session_path, check=False)

    if not animal_names:
        return

    animals_tree_data: dict[str, tuple[int, list[str]]] = {}
    for animal in animal_names:
        _, sessions = list_session_datetime(raw_path / animal)
        absent = missing_ephys_sessions(animal, sessions) if missing else []
        leaves = list(sessions) + [f"[yellow]{s}[/] [dim](remote-only)" for s in absent]
        animals_tree_data[animal] = (len(sessions), leaves)

    print_session_tree(f"[bold]{raw_path}", animals_tree_data)


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
    Kilosort every not-yet-processed session of the given animals/sessions.
    An animal name expands to its ephys sessions (with a `_g?` gate folder) on the server.
    Session names given explicitly are always included.

    \b
    A session is skipped if it already has a `_ksort` folder or a pyaldata/nwb file on the server.
    For every remaining session: download (no video), convert to pyaldata,
    upload back to the server, then replace the bulky local raw data with
    a light copy (like `dl-light`).

    \b
    Example usage:
        `yes | bnd ks M123 M124` kilosorts all pending sessions of M123 and M124
        `yes | bnd ks M123_2000_02_03_14_15 M123_2024_01_01_10_00` kilosorts just those sessions
    """
    _check_processing_dependencies()
    from .pipeline.batch import run_kilosort_batch

    run_kilosort_batch(targets)


# =================================== Config ============================================


@app.command()
def show_config():
    """
    Show the contents of the config file.
    """
    config = _load_config()
    print(f"bnd version {get_version()}")
    print(f"bnd source code is at {_get_package_path()}", end="\n\n")
    for attr, value in config.__dict__.items():
        print(f"{attr}: {value}")


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
