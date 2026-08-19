# bnd : Behavioural & Neural Data

A **lightweight** collection of functions for managing the experimental neuroscience data. A CLI tool called `bnd` for easy access in the terminal.


## Setting up

> **Upgrading from an older version?** Earlier releases were installed with pipx. Remove that
> first so the two installs don't shadow each other:
> ```shell
> pipx uninstall bnd
> ```

### 1. Install `bnd`

[uv](https://docs.astral.sh/uv/) installs `bnd` in an isolated environment and makes the CLI available system-wide.


1. Install uv if you don't have it:
   ```shell
   # Linux / macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Restart your terminal afterwards (or run `uv tool update-shell`) so the tool directory is on your PATH.
2. Deactivate conda environments:
  ```shell
   conda deactivate
  ```
   Even better, disable auto-activating of the `base` conda environment:
   ```shell
   conda config --set auto_activate_base false
   ```
3. Install `bnd`:
   ```shell
   # Lightweight (upload, download, config only — fast install):
   uv tool install "bnd @ git+https://github.com/AtMostafa/bnd.git"

   # Full install with processing dependencies (NWB, kilosort, pyaldata):
   uv tool install "bnd[processing] @ git+https://github.com/AtMostafa/bnd.git"
   ```
   To install a specific branch (e.g. for testing):
   ```shell
   uv tool install "bnd[processing] @ git+https://github.com/AtMostafa/bnd.git@seperate-ks-env"
   ```

4. Verify:
   ```shell
   bnd --help
   ```

To **update** to the latest commits:
```shell
conda deactivate
uv tool upgrade bnd --reinstall
```
`bnd` tracks a git branch rather than a pinned version, so `--reinstall` is needed to make uv re-fetch and pick up the newest commits.


### 2. Set up Kilosort (separate conda env)

Kilosort runs in its own conda environment — `bnd` invokes it via `conda run -n kilosort ...`.

1. Create and activate the env:
   ```shell
   conda create -n kilosort python=3.10 pip
   conda activate kilosort
   ```
2. Install Kilosort following the [official instructions](https://github.com/MouseLand/Kilosort):
   ```shell
   python -m pip install "kilosort[gui]"
   ```
   Or minimal (no GUI):
   ```shell
   python -m pip install kilosort
   ```
3. Install GPU-enabled PyTorch (example for CUDA 11.8):
   ```shell
   conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia
   ```

> **Note:** If your env is not named `kilosort`, set the environment variable `BND_KILOSORT_ENV` to
> the env name before running `bnd`.

### 3. Configure `bnd`

```shell
bnd init    # Provide the path to local and remote data storage
bnd --help  # Start reading about the functions!
```

## Example usage

Complete your experimental session on animal M099. Then:

```shell
bnd up M099
```

Now, you want to process your data into a pyaldata format. Its a good idea to do this on one of the lab workstations:

```shell
bnd dl M099_2025_01_01_10_00 -v  # Downloads everything
bnd to-pyal M099_2025_01_01_10_00  # Run kilosort, nwb conversion, and pyaldata conversion
bnd up M099_2025_01_01_10_00  # Uploads new files to server
```

If you want specific things during your pipeline (e.g., dont run kilosort, use a custom channel map) read the API below.

## API

## Config

### `bnd --version` / `bnd -v`

Print the upstream repo URL and the installed `bnd` version, then exit.

### `bnd init`

Create a .env file (if there isnt one) to store the paths to the local and remote data storage.

### `bnd show-config`

Show the contents of the config file.

## Data Transfer

### `bnd up <session_or_animal_name>`

Upload data from session or animal name to the server. If the file exists on the server, it won't be replaced. Every file in the session folder will get uploaded.

Example usage to upload everything of a given session:

```shell
bnd up M017_2024_03_12_18_45
bnd up M017
```

### `bnd dl <session>`

Download experimental data from a given session from the remote server.

Example usage to download everything:

```shell
bnd dl M017_2024_03_12_18_45 -v  # will download everything, including videos
bnd dl M017_2024_03_12_18_45  # will download everything, except videos
bnd dl M017_2024_03_12_18_45 --max-size=50  # will download files smaller than 50MB
```

### `bnd dl-light <session>`

Download a session, like `dl`, but always skipping bulky raw data: video files, SpikeGLX
data files (`..._g?_...`, except their `*.meta`), anything inside a `..._ksort` folder, and
anything inside a `..._camera`/`..._cameras` folder.

Example usage:

```shell
bnd dl-light M017_2024_03_12_18_45  # downloads everything except the bulky raw data
bnd dl-light M017_2024_03_12_18_45 --max-size=50  # also skip any remaining file bigger than 50MB
```

## Listing

### `bnd ls [animal_or_session] [-m]`

List the sessions available locally for one animal or all of them. If a full session name is
given instead, show that session's file sizes. Pass `-m`/`--missing` to also flag ephys
sessions (with a SpikeGLX `_g?` gate folder) that exist on the remote server but not locally.

Example usage:

```shell
bnd ls  # lists every animal and its sessions
bnd ls M170  # lists the sessions of M170 only
bnd ls M170_2024_03_12_18_45  # shows that session's files
bnd ls -m  # also flags remote ephys sessions missing locally
bnd ls M170 -m  # same, for M170 only
```

## Pipeline

### `bnd to-pyal <session>`

Convert session data into a pyaldata dataframe and saves it as a .mat

If no .nwb file is present it will automatically generate one and if a nwb file is present it will skip it. If you want to generate a new one run `bnd to-nwb`

If no kilosorted data is available it will not kilosort by default. If you want to kilosort add the flag `-k`

Example usage:

```shell
bnd to-pyal M037_2024_01_01_10_00  # Kilosorts data, runs nwb and converts to pyaldata
bnd to-pyal M037_2024_01_01_10_00 -K  # converts to pyaldata without kilosorting (if no .nwb file is present)
bnd to-pyal M037_2024_01_01_10_00 -c  # Use custom mapping during nwb conversion if custom_map.json is available (see template in repo). -C uses available default mapping
```

### `bnd to-nwb <session>`

Convert session data into a nwb file and saves it as a .nwb

If no kilosorted data is available it will not kilosort by default. If you want to kilosort add the flag `-k`

Example usage:

```shell
bnd to-nwb M037_2024_01_01_10_00  # Kilosorts data and run nwb
bnd to-nwb M037_2024_01_01_10_00 -K  # converts to nwb without kilosorting (if no .nwb file is present)
bnd to-nwb M037_2024_01_01_10_00 -c  # Use custom mapping during conversion if custom_map.json is available (see template in repo). Option `-C` uses available default mapping
```

### `bnd ksort <session>`

Kilosorts data from a single session on all available probes and recordings

Example usage:

```shell
bnd ksort M037_2024_01_01_10_00
```

### `bnd ks <targets...>`

Batch-kilosort every not-yet-processed session for one or more animals and/or sessions.
An animal name (`M123`) expands to all of that animal's sessions on the remote server. A
session is skipped if it already has a `_ksort` folder or a pyaldata/nwb file.

For every remaining session it downloads the data (no video), runs `to-pyal` with kilosort
and custom mapping, uploads the results back to the server, then replaces the bulky local
raw data with a light copy (like `dl-light`). Problematic sessions are skipped and all
issues are logged in a summary at the end.

Example usage:

```shell
yes | bnd ks M123 M124  # kilosorts every pending session of M123 and M124
yes | bnd ks M123_2024_01_01_10_00 M123_2024_01_02_10_00  # kilosorts just that session
yes | bnd ks M123  # auto-confirm the upload prompts
```

# TODOs:

- Add `AniposeInterface` in nwb conversion
- Implement Npx2.0 functionality
