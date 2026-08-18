"""This module contains functions for uploading and downloading data to and from the server."""

import os
import shutil
from pathlib import Path

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .config import _load_config, list_session_datetime
from .logger import set_logging

logger = set_logging(__name__)


def _copy_robust(src: Path, dst: Path, *, resume: bool = True) -> None:
    """Copy `src` to `dst` via a `.part` sibling, resuming a previous partial copy.

    Writing straight to `dst` means an interrupted transfer leaves a truncated file.
    Data lands in `dst.part` instead and is renamed into place only once its size matches the source.
    A failed copy raises; the `.part` file is left behind so the next run resumes from it.
    """
    _COPY_BUF = 8 * 1024 * 1024  # the stdlib default (64 KiB-1 MiB) stalls on high-latency SMB/NFS
    tmp = dst.with_name(dst.name + ".part")
    total = src.stat().st_size

    offset = tmp.stat().st_size if (resume and tmp.exists()) else 0
    if offset > total:  # source changed
        offset = 0
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(src.name, total=total, completed=offset)
        with open(src, "rb") as fsrc, open(tmp, "r+b" if offset else "wb") as fdst:
            fsrc.seek(offset)
            fdst.seek(offset)
            fdst.truncate(offset)
            buf = memoryview(bytearray(_COPY_BUF))
            while n := fsrc.readinto(buf):
                fdst.write(buf[:n])
                progress.advance(task, n)
            fdst.flush()
            os.fsync(fdst.fileno())

    copied = tmp.stat().st_size
    if copied != total:
        raise OSError(f'"{src.name}": copied {copied} of {total} bytes')

    os.replace(tmp, dst)
    try:
        shutil.copystat(src, dst)  # best effort: often denied on network mounts
    except OSError:
        pass


def _upload_file(local_file: Path, remote_file: Path):
    """Uploads a file and triggers assertion if they already exist

    Parameters
    ----------
    local_file: Path
        local path of the file to upload
    remote_file: Path
        remote path of the file to upload
    """

    assert not remote_file.exists(), "Remote file already exists. This should not happen."

    # Ensure the destination directory exists
    remote_file.parent.mkdir(parents=True, exist_ok=True)
    _copy_robust(local_file, remote_file)
    logger.info(f'Uploaded "{local_file.name}"')


def upload_session(session_name: str) -> None:
    """
    Upload a session to the server.
    Every file in the session folder will get uploaded.
    No file on the server will get overwritten
    """
    config = _load_config()
    remote_session_path = config.get_remote_session_path(session_name)
    local_session_path = config.get_local_session_path(session_name)

    local_files = list(local_session_path.rglob("*"))
    remote_files = list(remote_session_path.rglob("*"))
    assert isinstance(
        remote_files, list
    ), "`remote_files` must be a list, otherwise the list comprehension below will break"
    pending_local_files = [
        file
        for file in local_files
        if config.convert_to_remote(file) not in remote_files 
        and file.is_file()
    ]
    if not pending_local_files:
        logger.info("No files to upload.")
        return

    # Check if file names follow the session name convention
    for file in pending_local_files:
        if not config.file_name_ok(file.name):
            logger.warning(f'Unusual file name: "{file.name}"')

    response = input(f"\nUpload session {session_name} (y/n)? ").strip().lower()
    if "n" in response:
        logger.info("Upload aborted.")
        return

    # Upload the files
    for file in pending_local_files:
        remote_file = config.convert_to_remote(file)
        assert not remote_file.exists(), "Remote file exists. This should never happen."

        _upload_file(local_file=file, remote_file=remote_file)

    logger.info("Upload complete.")


def download_session(session_name: str, file_extension: str, max_size_MB: float, do_video: bool) -> None:
    """
    Download a session from the server.
    """
    config = _load_config()

    if not config.file_name_ok(session_name):
        # bad session name, try to find a session with a similar name
        remote_animal_path = config.get_remote_animal_path(session_name)
        _,session_list = list_session_datetime(remote_animal_path)
        match_session = [session for session in session_list if session_name in session]
        if match_session:
            session_name = match_session[0]
            response = input(f"\nDid you mean {session_name} (y/n)? ").strip().lower()
            if "n" in response:
                logger.error("Download aborted!")
                return
            logger.info(f"Session name corrected to {session_name}")
        else:
            logger.error("Bad session name. Download aborted!")

    if int(max_size_MB) <= 0:
        max_size = float("inf")
    else:
        max_size = max_size_MB * 1024 * 1024  # convert to bytes

    remote_session_path = config.get_remote_session_path(session_name)
    local_session_path = config.get_local_session_path(session_name)
    if local_session_path.exists():
        logger.info(f"Session {session_name} exists locally.")

    # Excluding directories as `rglob()` returns directories as well
    # Including only files with the right extension.
    remote_files = [file for file in remote_session_path.rglob(f"*{file_extension}") if file.is_file()]

    for file in remote_files:
        if file.suffix in config.video_formats and not do_video:
            logger.info(f'"{file.name}" is a video file. Skipping.')
            continue  # skip video files

        if file.stat().st_size < max_size:
            local_file = config.convert_to_local(file)
            if local_file.exists():
                logger.warning(f'"{file.name}" exists locally. Skipping.')
                continue
            # Ensure the destination directory exists
            local_file.parent.mkdir(parents=True, exist_ok=True)
            _copy_robust(file, local_file)
            logger.info(f'Downloaded "{file.name}"')
        else:
            logger.info(f'"{file.name}" is too large. Skipping.')

    logger.info("Download complete.")


def download_session_light(session_name: str, max_size_MB: float = 0) -> None:
    """
    Download a session from the server, like `download_session`, but skipping bulky raw data.

    The following are always skipped, regardless of `max_size_MB`:
    - video files,
    - SpikeGLX (`..._g?_...`) data files except the `*.meta` metadata files,
    - anything inside a `..._ksort` folder,
    - anything inside a `..._camera` or `..._cameras` folder.

    Parameters are the same as `download_session` (videos are never downloaded here).
    """
    config = _load_config()

    if not config.file_name_ok(session_name):
        # bad session name, try to find a session with a similar name
        remote_animal_path = config.get_remote_animal_path(session_name)
        _, session_list = list_session_datetime(remote_animal_path)
        match_session = [session for session in session_list if session_name in session]
        if match_session:
            session_name = match_session[0]
            response = input(f"\nDid you mean {session_name} (y/n)? ").strip().lower()
            if "n" in response:
                logger.error("Download aborted!")
                return
            logger.info(f"Session name corrected to {session_name}")
        else:
            logger.error("Bad session name. Download aborted!")
            return

    if int(max_size_MB) <= 0:
        max_size = float("inf")
    else:
        max_size = max_size_MB * 1024 * 1024  # convert to bytes

    remote_session_path = config.get_remote_session_path(session_name)
    local_session_path = config.get_local_session_path(session_name)
    if local_session_path.exists():
        logger.info(f"Session {session_name} exists locally.")

    # Excluding directories as `rglob()` returns directories as well
    # Including only files with the right extension.
    remote_files = [file for file in remote_session_path.rglob("*.*") if file.is_file()]

    for file in remote_files:
        if file.suffix in config.video_formats:
            logger.info(f'"{file.name}" is a video file. Skipping.')
            continue  # skip video files

        # Path components of the file, relative to the session folder.
        rel_parts = file.relative_to(remote_session_path).parts
        dir_parts = rel_parts[:-1]

        if any(config.KSORT_RE.search(part) for part in dir_parts):
            logger.info(f'"{file.name}" is inside a kilosort folder. Skipping.')
            continue

        if any(config.CAMERA_RE.search(part) for part in dir_parts):
            logger.info(f'"{file.name}" is inside a camera folder. Skipping.')
            continue

        # Under a SpikeGLX gate path (folder or file name), keep only the *.meta files.
        if any(config.GATE_RE.search(part) for part in rel_parts) and file.suffix != ".meta":
            logger.info(f'"{file.name}" is raw gate data (keeping only *.meta). Skipping.')
            continue

        if file.stat().st_size < max_size:
            local_file = config.convert_to_local(file)
            if local_file.exists():
                logger.warning(f'"{file.name}" exists locally. Skipping.')
                continue
            # Ensure the destination directory exists
            local_file.parent.mkdir(parents=True, exist_ok=True)
            _copy_robust(file, local_file)
            logger.info(f'Downloaded "{file.name}"')
        else:
            logger.info(f'"{file.name}" is too large. Skipping.')

    logger.info("Download complete.")


def download_animal(animal_name: str, file_extension: str, max_size_MB: float = 0, do_video: bool = False) -> None:
    """
    Download a all the data of an animal from the server.
    animal_name: str = 'M123'
        Name of the animal to download
    file_extension: str = '.log'
        One file type to download
    max_size_MB: float = 0
        Maximum size in MB. Any smaller file will be downloaded. Zero mean infinite size
    do_video: bool = False
        Download video files as well, if they are smaller than `max_size_MB`. No video files by default.
    """
    config = _load_config()

    remote_animal_path = config.get_remote_animal_path(animal_name)
    _,session_list = list_session_datetime(remote_animal_path)
    for session_name in session_list:
        download_session(session_name, file_extension, max_size_MB, do_video)
