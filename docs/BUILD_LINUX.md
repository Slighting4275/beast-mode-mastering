# BUILD_LINUX.md

# Beast Mode Mastering Linux Build and Run Guide

This file is the corrected step-by-step Linux setup guide for Beast Mode Mastering.

This guide is written for people who want extremely clear instructions and do not want to guess what to install, where to go, or what to type.

This project is a Python desktop application for Linux. In normal Linux terms, the practical "build" process is not a giant traditional compile process like a big C++ project. The normal path is:

1. install the system packages the app depends on
2. download or clone the repository
3. move into the project folder
4. create a Python virtual environment
5. activate that virtual environment
6. install the Python dependencies with `pip`
7. install the local project package into that virtual environment
8. run the application
9. optionally install the desktop launcher and applications-menu integration

If you follow the steps in order, you should end up with a working Linux installation of the project.

---

# Important correction

This repository uses a `src/` layout.

That means this step is required:

```bash
python -m pip install -e .
```

If you skip that step, the dependencies may install correctly, but Python still will not be able to import the local package `beast_mode_mastering`, and launching the app with:

```bash
python -m beast_mode_mastering.app
```

will fail with `ModuleNotFoundError`.

On Linux Mint and some other systems, especially when `pyenv` is installed, the bare `python` command may not work before the virtual environment is active. On those systems, use `python3 -m venv .venv` to create the environment.

---

# What this application needs

The project expects these things to exist on your Linux system:

- Python 3.10 or newer
- `pip`
- virtual environment support (`venv`)
- Python development headers
- PortAudio runtime and development files
- `libsndfile`
- FFmpeg command-line tools
- a basic C/C++ toolchain in case a Python package needs to build a fallback wheel locally
- optional desktop integration tools if you want the launcher, applications-menu entry, and icon install script to render PNG icon sizes correctly

---

# Before you begin

Make sure you know which Linux family you are on.

Use the section that matches your distro:

- Arch / Manjaro / EndeavourOS
- Ubuntu / Debian / Linux Mint
- Fedora
- RHEL / Rocky / Alma / CentOS Stream

If you are not sure which one you are running, you can check with:

```bash
cat /etc/os-release
```

Look for the distro name in the output.

---

# What you are going to do

No matter which distro you are on, the process is basically:

- install system packages
- download the project
- enter the project folder
- create `.venv`
- activate `.venv`
- install Python requirements
- install the local package with `pip install -e .`
- launch the app
- optionally install the desktop launcher and applications-menu entry

---

# Repo source

You need the project files on your computer.

There are two normal ways to do that.

## Option 1: clone the GitHub repo

This is the normal developer method.

```bash
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
```

## Option 2: download the GitHub zip

This is fine if you do not want to use `git` yet.

- open the repo in GitHub
- click the green **Code** button
- click **Download ZIP**
- extract the zip somewhere on your Linux system
- open a terminal in the extracted folder

Example:

```bash
cd "/path/to/the/extracted/beast-mode-mastering-folder"
```

If you plan to contribute code back to the repo, cloning with `git` is better.

---

# Common Python setup flow

After the correct system packages are installed for your distro, the common Python setup is:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

On some distros, `python` may be the main Python command instead of `python3`. If your distro uses `python` for Python 3, that is fine. The important part is that the virtual environment gets created successfully. On Linux Mint systems where `pyenv` interferes with `python`, use `python3 -m venv .venv` exactly as written above.

---

# Arch / Manjaro / EndeavourOS

This section is for:

- Arch Linux
- Manjaro
- EndeavourOS
- similar Arch-based systems

## Step 1: install system packages

Run:

```bash
sudo pacman -S --needed git python python-pip ffmpeg portaudio libsndfile base-devel
```

What those packages are for:

- `git` = needed if you want to clone the repo
- `python` = Python itself
- `python-pip` = Python package installer
- `ffmpeg` = audio/media command-line support
- `portaudio` = low-level audio I/O dependency
- `libsndfile` = audio file reading/writing support
- `base-devel` = build tools for fallback Python package builds

## Step 2: get the repo

If you are cloning:

```bash
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
```

If you downloaded a zip, change into the extracted folder.

## Step 3: create the virtual environment

Run:

```bash
python -m venv .venv
```

This creates a folder named `.venv` inside the project.

## Step 4: activate the virtual environment

Run:

```bash
. .venv/bin/activate
```

After this, your shell is using the Python environment just for this project.

## Step 5: upgrade pip

Run:

```bash
python -m pip install --upgrade pip
```

## Step 6: install project Python dependencies

Run:

```bash
python -m pip install -r requirements.txt
```

## Step 7: install the local project package

Run:

```bash
python -m pip install -e .
```

## Step 8: launch the app

Run:

```bash
python -m beast_mode_mastering.app
```

If the app opens, the build worked.

---

# Ubuntu / Debian / Linux Mint

This section is for:

- Ubuntu
- Debian
- Linux Mint
- Pop!_OS
- similar Debian-based systems

## Step 1: update package lists

Run:

```bash
sudo apt update
```

## Step 2: install system packages

Run:

```bash
sudo apt install -y git python3 python3-venv python3-pip python3-dev portaudio19-dev libsndfile1 ffmpeg build-essential
```

What those packages are for:

- `git` = repo cloning
- `python3` = Python itself
- `python3-venv` = virtual environment support
- `python3-pip` = Python package installer
- `python3-dev` = Python development headers
- `portaudio19-dev` = PortAudio development package
- `libsndfile1` = sound file library
- `ffmpeg` = media/audio tools
- `build-essential` = compiler and basic build tools

## Step 3: get the repo

If you are cloning:

```bash
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
```

If you downloaded a zip, extract it and change into the extracted folder.

## Step 4: create the virtual environment

Run:

```bash
python3 -m venv .venv
```

## Step 5: activate the virtual environment

Run:

```bash
. .venv/bin/activate
```

## Step 6: upgrade pip

Run:

```bash
python -m pip install --upgrade pip
```

## Step 7: install project Python dependencies

Run:

```bash
python -m pip install -r requirements.txt
```

## Step 8: install the local project package

Run:

```bash
python -m pip install -e .
```

## Step 9: launch the app

Run:

```bash
python -m beast_mode_mastering.app
```

If the GUI opens, the setup worked.

---

# Fedora

This section is for Fedora Linux.

## Step 1: install system packages

Run:

```bash
sudo dnf install -y git python3 python3-pip python3-devel portaudio-devel libsndfile ffmpeg-free gcc gcc-c++ make redhat-rpm-config
```

What those packages are for:

- `git` = repo cloning
- `python3` = Python itself
- `python3-pip` = Python package installer
- `python3-devel` = Python headers
- `portaudio-devel` = PortAudio development package
- `libsndfile` = sound file library
- `ffmpeg-free` = FFmpeg package from Fedora’s normal package path
- `gcc`, `gcc-c++`, `make`, `redhat-rpm-config` = build toolchain

## Step 2: get the repo

If cloning:

```bash
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
```

If you downloaded the zip, extract it and move into the extracted folder.

## Step 3: create the virtual environment

Run:

```bash
python3 -m venv .venv
```

## Step 4: activate the virtual environment

Run:

```bash
. .venv/bin/activate
```

## Step 5: upgrade pip

Run:

```bash
python -m pip install --upgrade pip
```

## Step 6: install Python dependencies

Run:

```bash
python -m pip install -r requirements.txt
```

## Step 7: install the local project package

Run:

```bash
python -m pip install -e .
```

## Step 8: launch the app

Run:

```bash
python -m beast_mode_mastering.app
```

---

# RHEL / Rocky / Alma / CentOS Stream

This section is for Enterprise Linux style systems:

- RHEL
- Rocky Linux
- AlmaLinux
- CentOS Stream

These systems often need a little more package repository setup than Arch, Debian, Ubuntu, Mint, or Fedora.

## Step 1: install the core system packages

Run:

```bash
sudo dnf install -y git python3 python3-pip python3-devel portaudio-devel libsndfile gcc gcc-c++ make redhat-rpm-config
```

## Step 2: make sure FFmpeg is available

FFmpeg is often handled differently on Enterprise Linux style systems.

You may need to enable EPEL and then standardize on an FFmpeg source such as RPM Fusion Free for your chosen Enterprise Linux target.

After FFmpeg is available, continue.

## Step 3: get the repo

If you are cloning:

```bash
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
```

If you downloaded a zip, extract it and change into the extracted folder.

## Step 4: create the virtual environment

Run:

```bash
python3 -m venv .venv
```

## Step 5: activate the virtual environment

Run:

```bash
. .venv/bin/activate
```

## Step 6: upgrade pip

Run:

```bash
python -m pip install --upgrade pip
```

## Step 7: install Python dependencies

Run:

```bash
python -m pip install -r requirements.txt
```

## Step 8: install the local project package

Run:

```bash
python -m pip install -e .
```

## Step 9: launch the app

Run:

```bash
python -m beast_mode_mastering.app
```

# Launching the application

Once the environment is installed, the normal way to launch the GUI is:

```bash
. .venv/bin/activate
python -m beast_mode_mastering.app
```

If the GUI opens, your setup is working.

# Optional desktop launcher / applications menu integration

The repository now includes desktop-integration files for Linux:

- `assets/icons/beast-mode-mastering.svg`
- `scripts/install_desktop_integration.sh`
- `scripts/uninstall_desktop_integration.sh`

This is optional. The normal Python setup and `python -m beast_mode_mastering.app` launch path still works without it.

## Linux Mint / Ubuntu / Debian extra packages for desktop integration

If you want the install script to render multiple PNG icon sizes and refresh the applications menu cleanly, install:

```bash
sudo apt update
sudo apt install -y librsvg2-bin desktop-file-utils
```

On other distros, install the distro-equivalent packages that provide `rsvg-convert` and `update-desktop-database`.

## Install the desktop launcher and menu entry

From the project root, run:

```bash
bash ./scripts/install_desktop_integration.sh
```

That installs:

- a launcher command in `~/.local/bin/beast-mode-mastering`
- a desktop file in `~/.local/share/applications/beast-mode-mastering.desktop`
- the app icon in `~/.local/share/icons/hicolor/`

After that, the app should appear in the applications menu as **Beast Mode Mastering**.

You can also launch it directly with:

```bash
"$HOME/.local/bin/beast-mode-mastering"
```

## Remove the desktop launcher and menu entry

If you want to remove the desktop integration later, run:

```bash
bash ./scripts/uninstall_desktop_integration.sh
```

# GUI WAV export

The GUI now includes an **Export WAV** button.

Normal GUI export flow:

1. launch the app
2. load an audio file
3. click **Export WAV**
4. choose the output directory and filename in the save dialog
5. save the mastered 24-bit WAV

# CLI export

The project also includes a command-line export path.

Example usage:

```bash
. .venv/bin/activate
python scripts/export_mastered_cli.py "/path/to/input.wav" "/path/to/output_mastered.wav"
```

Example with home-directory paths:

```bash
. .venv/bin/activate
python scripts/export_mastered_cli.py "$HOME/Music/input.wav" "$HOME/Music/output_mastered.wav"
```

# Recommended first-run check

After installing dependencies, it is a good idea to verify that Python can import the project before launching the GUI.

From the project root:

```bash
. .venv/bin/activate
python -m pip install -e .
python -c "import beast_mode_mastering.app; print('import OK')"
```

If that prints `import OK`, try launching the application:

```bash
. .venv/bin/activate
python -m beast_mode_mastering.app
```

# Full example from zero to running

If you want a plain example, this is the normal Ubuntu / Debian / Linux Mint path from zero to running:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev portaudio19-dev libsndfile1 ffmpeg build-essential
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m beast_mode_mastering.app
```

This is the normal Arch / Manjaro / EndeavourOS path from zero to running:

```bash
sudo pacman -S --needed git python python-pip ffmpeg portaudio libsndfile base-devel
git clone https://github.com/Slighting4275/beast-mode-mastering.git
cd beast-mode-mastering
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m beast_mode_mastering.app
```

# Troubleshooting

## `python -m pip install -r requirements.txt` fails

Check all of the following:

- you are inside the project folder
- the virtual environment is activated
- the distro-specific system packages were installed first
- the Python development headers are installed
- the basic C/C++ build tools are installed

Typical missing pieces:

- Debian / Ubuntu / Mint: `python3-dev` or `build-essential`
- Arch-based distros: `base-devel`
- Fedora / EL-family systems: `python3-devel`, `gcc`, `gcc-c++`, `make`, or `redhat-rpm-config`

## The app will not launch

Check:

- that `.venv` is activated
- that requirements installed successfully
- that the local project package was installed with `python -m pip install -e .`
- that you are launching from the project root
- that Python can import the app module

Try:

```bash
. .venv/bin/activate
python -m pip install -e .
python -c "import beast_mode_mastering.app; print('import OK')"
```

## Audio playback issues

If the GUI opens but playback does not work correctly, confirm:

- PortAudio was installed correctly
- your Linux audio stack works normally outside the app
- your user account has a valid default output device

## Desktop launcher or icon issues

If the app runs but the applications-menu entry or icon does not show correctly, check all of the following:

- you ran `bash ./scripts/install_desktop_integration.sh` from the project root
- on Debian / Ubuntu / Linux Mint, `librsvg2-bin` and `desktop-file-utils` are installed
- the desktop file exists at `~/.local/share/applications/beast-mode-mastering.desktop`
- the icon files exist under `~/.local/share/icons/hicolor/`

If needed, rerun:

```bash
bash ./scripts/install_desktop_integration.sh
```

## FFmpeg-related confusion

FFmpeg is part of the expected Linux toolchain for this project. If your distro handles FFmpeg differently, standardize that first and then continue with the Python setup.

## Import path problems

Run commands from the repository root and make sure the local package was installed into the active virtual environment.

Correct:

```bash
python -m pip install -e .
python -m beast_mode_mastering.app
```

Wrong:

Running the app command from some unrelated directory where Python cannot see the local project package, or skipping installation of the local package when using the repo’s `src/` layout.

# Contributor note

If you are reporting a Linux build problem, include all of the following:

- distro and distro version
- Python version
- exact commands you ran
- exact error output
- whether the failure happened during system package install, pip install, import check, launch, playback, or export

That makes debugging much faster.
