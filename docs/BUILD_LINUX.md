# Linux build / run dependencies

This project is a Python desktop application. In practice, the Linux "build" path is:
1. Install system packages
2. Create a Python virtual environment
3. Install Python dependencies with `pip`

## Common Python requirements
- Python 3.10+
- pip
- venv support
- Python development headers
- PortAudio runtime + development headers
- libsndfile runtime
- FFmpeg CLI tools
- a C/C++ toolchain for any fallback wheel builds

## Arch / Manjaro / EndeavourOS
System packages:
```bash
sudo pacman -S --needed git python python-pip ffmpeg portaudio libsndfile base-devel
```

Create environment and install:
```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ubuntu / Debian / Linux Mint
System packages:
```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev portaudio19-dev libsndfile1 ffmpeg build-essential
```

Create environment and install:
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Fedora
System packages:
```bash
sudo dnf install -y git python3 python3-pip python3-devel portaudio-devel libsndfile ffmpeg-free gcc gcc-c++ make redhat-rpm-config
```

Create environment and install:
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## RHEL / Rocky / Alma / CentOS Stream
Enable EPEL first if needed, then add RPM Fusion Free if you want the usual FFmpeg workflow on Enterprise Linux.

Example package path:
```bash
sudo dnf install -y git python3 python3-pip python3-devel portaudio-devel libsndfile gcc gcc-c++ make redhat-rpm-config
```

Then install FFmpeg from the repository path you standardize on for your EL build target.

Create environment and install:
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Launch
```bash
. .venv/bin/activate
python -m beast_mode_mastering.app
```

## CLI export
```bash
. .venv/bin/activate
python scripts/export_mastered_cli.py "/path/to/input.wav" "/path/to/output_mastered.wav"
```
