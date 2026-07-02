# Installation Guide

This guide provides comprehensive installation instructions for `py10x-core`, including all prerequisites and setup steps for different use cases.

See also the [documentation map in README.md](README.md#documentation-map).

## Prerequisites

### Core Requirements

- **Python 3.12 (recommended), 3.11+ supported** - Install via UV for best experience
- **[UV](https://docs.astral.sh/uv/)** - Python installer and package manager (recommended)
- **Git** - For cloning the repository

### Optional: Building Native Dependencies from Source

`py10x-core` depends on `py10x-kernel` and `py10x-infra`, which contain native (C++) extension modules. **`pip` and `uv` install prebuilt wheels for these from PyPI**, so the typical user does not need a C++ toolchain.

A C++20 compiler is only required if you are:

1. Building `py10x-kernel` or `py10x-infra` **from source** (e.g. against a local checkout of those repos), **or**
2. Installing on a platform / Python-version combination for which **no prebuilt wheel is published**, in which case `pip` falls back to compiling the sdist.

If either applies, install one of:

- **Linux**: GCC 10+ or Clang 10+
- **macOS**: Xcode Command Line Tools (Clang) or GCC 10+
- **Windows**: MSVC 2022+ (Visual Studio 2022 Build Tools or full IDE) with the *Desktop development with C++* workload

### Optional UI Dependencies

- **Node.js and npm** (for Rio UI backend)
  - Required if you plan to use Rio UI components
  - Download from [nodejs.org](https://nodejs.org/)

### Optional Database Dependencies

**Traitable Store backends** (for `infra_10x` tests and persistence examples):

- `core_10x` tests use the **in-process** Traitable Store — no external database.
- `infra_10x` tests use the **MongoDB-backed** store (`MongoStore`, implemented in `infra_10x`).
  Those tests require a local **passwordless MongoDB** instance on **port 27017** (replica set for
  transactions). See platform setup below for install commands.

Other docs link here for store requirements; do not duplicate the full blurb elsewhere.

## Installation Methods

### Install UV and Python

First, install UV (which includes Python installation):

#### Linux/macOS
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add UV to PATH (add to your shell profile); the installer prints the
# actual path it used — use that if it differs.
export PATH="$HOME/.local/bin:$PATH"

# Install Python 3.12
uv python install 3.12

# Set Python 3.12 as default
uv python pin 3.12
```

#### Windows (PowerShell)
```powershell
# Install UV
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install Python 3.12
uv python install 3.12

# Set Python 3.12 as default
uv python pin 3.12
```

#### Verify Installation
```bash
# Check UV version
uv --version

# Check Python version
python --version  # Should show 3.12.x
```

### Development Installation (Recommended)

For developers who want to contribute to `py10x-core` or need all features (including local C++
siblings from `../cxx10x`):

```bash
# Clone the repository (and cxx10x sibling if building kernel/infra from source)
git clone https://github.com/10x-software/py10x.git
cd py10x

# Full dev setup — installs py10x-core editable + local cxx10x siblings
uv-sync py10x-core-dev --all-extras
uv-run pytest -q   # run in the prepared venv
```

`uv-sync` drives `uv pip install` with dependency-source **profiles** (see
[`dev_10x/README.md`](dev_10x/README.md)); it does not mutate `pyproject.toml`. Plain `uv sync` is
not the canonical multi-repo dev path.

For lighter profiles (released wheels, git `main` siblings only), other `uv-sync` profiles, and
release promotion (`xx-promote`), see [`dev_10x/README.md`](dev_10x/README.md).

### User Installation

For users who just want to use `py10x-core`:

```bash
# Install from PyPI (when available)
pip install py10x-core[rio]    # With Rio UI backend
pip install py10x-core[qt]     # With Qt6 UI backend
pip install py10x-core[rio,qt] # With both UI backends

# Or install from source
git clone https://github.com/10x-software/py10x.git
cd py10x
pip install .
```

## Platform-Specific Setup

### Linux

#### Ubuntu/Debian
```bash
# Install Git (preinstalled on most desktop images but absent from minimal/server/container ones).
sudo apt update
sudo apt install git

# Optional: C++ toolchain — only needed if you build py10x-kernel / py10x-infra
# from source, or if no prebuilt wheel exists for your platform/Python combo.
sudo apt install build-essential g++-10

# Install MongoDB (for testing and examples) - optional
# Import the public key
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
# Add MongoDB repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/8.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
# Install MongoDB
sudo apt update
sudo apt install -y mongodb-org
# Start MongoDB service
sudo systemctl start mongod
sudo systemctl enable mongod

# Install Node.js (for Rio UI) - optional
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### Fedora/CentOS/RHEL
```bash
# Install Git (preinstalled on most desktop images but absent from minimal/server/container ones).
sudo dnf install git

# Optional: C++ toolchain — only needed if you build py10x-kernel / py10x-infra
# from source, or if no prebuilt wheel exists for your platform/Python combo.
sudo dnf install gcc-c++ gcc

# Install MongoDB (for testing and examples) - optional
# Create MongoDB repository file
cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-8.0.repo
[mongodb-org-8.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/8.0/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-8.0.asc
EOF
# Install MongoDB
sudo dnf install -y mongodb-org
# Start MongoDB service
sudo systemctl start mongod
sudo systemctl enable mongod

# Install Node.js (for Rio UI) - optional
sudo dnf install nodejs npm
```

### macOS

```bash
# Install Xcode Command Line Tools — provides Git on macOS.
# Also provides Clang (C++ toolchain), which is only needed if you build
# py10x-kernel / py10x-infra from source or no prebuilt wheel exists for
# your platform/Python combo. Either way, this single command is the
# standard macOS dev bootstrap and is recommended.
xcode-select --install

# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install MongoDB (for testing and examples) - optional
brew tap mongodb/brew
brew install mongodb-community
# Start MongoDB service
brew services start mongodb-community

# Install Node.js (for Rio UI) - optional
brew install node
```

### Windows

WinGet ships with Windows 10 1809+ and Windows 11, so no extra package manager bootstrap is needed.
Run the commands below from an **elevated PowerShell** (Run as Administrator) when installing system-wide packages — Git for Windows, Visual Studio Build Tools, MongoDB, and Node.js all install machine-scope.

The `--accept-package-agreements`, `--accept-source-agreements`, and `--silent` flags pre-answer every WinGet prompt so the install runs unattended; drop `--silent` if you want to watch progress. For Visual Studio Build Tools, the `--quiet --wait` part inside `--override` is forwarded to the VS bootstrapper so it also installs without prompting. Add `--disable-interactivity` for fully scripted runs (aborts rather than prompts on any unexpected question).

#### Using WinGet
```powershell
# Install Git for Windows (also bundles Git Bash, useful for copy-pasting POSIX snippets).
winget install --id Git.Git `
  --accept-package-agreements --accept-source-agreements --silent

# Optional: Visual Studio Build Tools with the C++ workload (MSVC, Windows SDK, CMake).
# Only needed if you build py10x-kernel / py10x-infra from source, or no prebuilt
# wheel exists for your platform/Python combo. The --override string is forwarded
# to the VS installer; without it you get only the Build Tools shell with no compiler.
winget install --id Microsoft.VisualStudio.2022.BuildTools `
  --accept-package-agreements --accept-source-agreements --silent `
  --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

# Install MongoDB (for testing and examples) - optional
winget install --id MongoDB.Server `
  --accept-package-agreements --accept-source-agreements --silent

# Install Node.js LTS (for Rio UI) - optional
winget install --id OpenJS.NodeJS.LTS `
  --accept-package-agreements --accept-source-agreements --silent
```

If you need the C++ workload and already have the full Visual Studio 2022 IDE installed, add the workload to it instead of installing Build Tools — open *Visual Studio Installer* → *Modify* → check **Desktop development with C++**.

#### Manual Installation
1. Download and install [Git for Windows](https://git-scm.com/download/win) (provides `git` and bundles Git Bash).
2. *Optional* — only if building native deps from source: download and install the [Visual Studio 2022 Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) and select the **Desktop development with C++** workload (or use the full [Visual Studio 2022](https://visualstudio.microsoft.com/downloads/) IDE with the same workload).
3. Download and install [MongoDB Community Server](https://www.mongodb.com/try/download/community) (for testing and examples) - optional
4. Download and install [Node.js](https://nodejs.org/) (for Rio UI) - optional

## Build System

`py10x-core` uses the `ux` abstraction layer that provides unified APIs across different UI backends (Rio and Qt6). The `ux` layer automatically:

- Detects available UI frameworks
- Selects the appropriate backend based on installed packages
- Falls back gracefully when dependencies are missing

### UI Backend Selection

You can override the automatic UI backend selection using environment variables:

```bash
# Force Rio UI backend
export UI_PLATFORM=Rio
uv sync --extra rio

# Force Qt6 UI backend
export UI_PLATFORM=Qt
uv sync --extra qt
```

## Verification

After installation, verify your setup:

```bash
# Check Python version (should be 3.12.x)
python --version

# Check UV version
uv --version

# Check C++ compiler — only relevant if you installed one for source builds
# of py10x-kernel / py10x-infra. Skip if you're using prebuilt wheels.
g++ --version  # Linux/macOS
cl.exe         # Windows — run from a "Developer PowerShell for VS 2022" prompt,
               # or from a regular shell after running vcvarsall.bat;
               # cl.exe is not on PATH in a plain PowerShell session.

# Check MongoDB (if installed)
mongod --version
# Test MongoDB connection
python -c "import pymongo; client = pymongo.MongoClient('localhost', 27017); print('MongoDB connection successful:', client.server_info()['version'])"

# Check Node.js (if using Rio UI)
node --version
npm --version

# Run basic tests
python -c "import core_10x; print('Core import successful')"
python -c "import ui_10x; print('UI import successful')"
python -c "import infra_10x; print('Infra import successful')"
```

## Troubleshooting

### C++ Compilation Issues

If you encounter C++ compilation errors:

1. **Check compiler version**: Ensure you have C++20 support
   ```bash
   g++ --version  # Should be 10.0 or higher
   ```

2. **Install development headers**: Make sure C++ standard library headers are available
   ```bash
   # Ubuntu/Debian
   sudo apt install build-essential

   # macOS - Xcode Command Line Tools should provide these
   xcode-select --install
   ```

### UI Backend Issues

If UI components fail to import:

1. **Rio UI**: Install Node.js and npm, then reinstall with Rio extras
   ```bash
   uv sync --extra rio
   ```

2. **Qt6 UI**: Install PyQt6 packages
   ```bash
   uv sync --extra qt
   ```

### Permission Issues

If you encounter permission errors during installation:

1. **Use virtual environment**: Always install in a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

2. **Use user installation**: Install to user directory instead of system
   ```bash
   pip install --user .
   ```

## Getting Help

- Check the [README.md](https://github.com/10x-software/py10x/blob/main/README.md) for overview and examples
- See [CONTRIBUTING.md](https://github.com/10x-software/py10x/blob/main/CONTRIBUTING.md) for development workflow
- See [dev_10x/README.md](dev_10x/README.md) for release engineering and dev dependency profiles
- Join our [Discord community](https://discord.gg/m7AQSXfFwf) for support
- Report issues on [GitHub](https://github.com/10x-software/py10x/issues)
