from pathlib import Path
from typing_extensions import Annotated

import typer
from rich import print

from beneuro_data.data_validation import validate_raw_session
from beneuro_data.data_transfer import upload_raw_session
from beneuro_data.video_renaming import rename_raw_videos_of_session
from beneuro_data.config import config

app = typer.Typer()


@app.command()
def validate_session(
    session_path: Annotated[
        Path, typer.Argument(help="Path to session directory. Can be relative or absolute")
    ],
    subject_name: Annotated[
        str,
        typer.Argument(
            help="Name of the subject the session belongs to. (Used for confirmation.)"
        ),
    ],
    processing_level: Annotated[
        str, typer.Argument(help="Processing level of the session. raw or processed.")
    ] = "raw",
    check_behavior: Annotated[
        bool,
        typer.Option(
            "--check-behavior/--ignore-behavior", help="Check behavioral data or not."
        ),
    ] = True,
    check_ephys: Annotated[
        bool,
        typer.Option("--check-ephys/--ignore-ephys", help="Check ephys data or not."),
    ] = True,
    check_videos: Annotated[
        bool,
        typer.Option("--check-videos/--ignore-videos", help="Check videos data or not."),
    ] = True,
):
    """
    Validate experiemental data in a given session.

    E.g. to check all kinds of data in the current working directory which is supposedly a session of subject called M017:

        `bnd validate-session . M017`
    """
    if processing_level != "raw":
        raise NotImplementedError("Sorry, only raw data is supported for now.")

    if all([not check_behavior, not check_ephys, not check_videos]):
        raise ValueError("At least one data type must be checked.")

    if not session_path.absolute().is_dir():
        raise ValueError("Session path must be a directory.")
    if not session_path.absolute().exists():
        raise ValueError("Session path does not exist.")

    validate_raw_session(
        session_path.absolute(),
        subject_name,
        check_behavior,
        check_ephys,
        check_videos,
    )


@app.command()
def rename_videos(
    session_path: Annotated[
        Path, typer.Argument(help="Path to session directory. Can be relative or absolute")
    ],
    subject_name: Annotated[
        str,
        typer.Argument(
            help="Name of the subject the session belongs to. (Used for confirmation.)"
        ),
    ],
    processing_level: Annotated[
        str, typer.Argument(help="Processing level of the session. raw or processed.")
    ] = "raw",
    verbose: Annotated[
        bool,
        typer.Option(help="Print the list of files that were renamed."),
    ] = False,
):
    """
    Rename the raw videos saved by Jarvis during a session to the convention we use.

    Example usage:

        `bnd rename-videos . M017 --verbose`

        `bnd rename-videos /absolute/path/to/session M017 --verbose`
    """
    if processing_level != "raw":
        raise NotImplementedError("Sorry, only raw data is supported for now.")

    if not session_path.absolute().is_dir():
        raise ValueError("Session path must be a directory.")
    if not session_path.absolute().exists():
        raise ValueError("Session path does not exist.")

    rename_raw_videos_of_session(
        session_path.absolute(),
        subject_name,
        verbose,
    )


@app.command()
def upload_session(
    local_session_path: Annotated[
        Path, typer.Argument(help="Path to session directory. Can be relative or absolute")
    ],
    subject_name: Annotated[
        str,
        typer.Argument(
            help="Name of the subject the session belongs to. (Used for confirmation.)"
        ),
    ],
    processing_level: Annotated[
        str, typer.Argument(help="Processing level of the session. raw or processed.")
    ] = "raw",
    include_behavior: Annotated[
        bool,
        typer.Option(
            "--include-behavior/--ignore-behavior", help="Upload behavioral data or not."
        ),
    ] = True,
    include_ephys: Annotated[
        bool,
        typer.Option("--include-ephys/--ignore-ephys", help="Upload ephys data or not."),
    ] = True,
    include_videos: Annotated[
        bool,
        typer.Option("--include-videos/--ignore-videos", help="Upload videos data or not."),
    ] = True,
):
    """
    Upload (raw) experimental data in a given session to the remote server.

    Example usage:
        `bnd upload-session . M017`
    """
    if processing_level != "raw":
        raise NotImplementedError("Sorry, only raw data is supported for now.")

    if all([not include_behavior, not include_ephys, not include_videos]):
        raise ValueError("At least one data type must be checked.")

    upload_raw_session(
        local_session_path.absolute(),
        subject_name,
        config.LOCAL_PATH,
        config.REMOTE_PATH,
        include_behavior,
        include_ephys,
        include_videos,
    )

    return True


@app.command()
def validate_sessions(
    subject_name: Annotated[str, typer.Argument(help="Subject name.")],
    processing_level: Annotated[
        str,
        typer.Argument(help="Processing level of the session. raw or processed."),
    ],
    check_behavior: Annotated[
        bool,
        typer.Option(
            "--check-behavior/--ignore-behavior", help="Check behavioral data or not."
        ),
    ] = True,
    check_ephys: Annotated[
        bool,
        typer.Option("--check-ephys/--ignore-ephys", help="Check ephys data or not."),
    ] = True,
    check_videos: Annotated[
        bool,
        typer.Option("--check-videos/--ignore-videos", help="Check videos data or not."),
    ] = True,
):
    """
    Validate (raw) experimental data in all sessions of a given subject.

    See options for which data to check and ignore.
    """

    if processing_level != "raw":
        raise NotImplementedError("Sorry, only raw data is supported for now.")

    if all([not check_behavior, not check_ephys, not check_videos]):
        raise ValueError("At least one data type must be checked.")

    subject_path = config.LOCAL_PATH / processing_level / subject_name

    for session_path in subject_path.iterdir():
        if session_path.is_dir():
            try:
                validate_raw_session(
                    session_path,
                    subject_name,
                    check_behavior,
                    check_ephys,
                    check_videos,
                )
            except Exception as e:
                print(f"[bold red]Problem with {session_path.name}: {e.args[0]}\n")
            else:
                print(f"[bold green]{session_path.name} looking good.\n")


@app.command()
def show_config():
    """
    Show the contents of the config file.
    """
    print(config.json(indent=4))


if __name__ == "__main__":
    app()
