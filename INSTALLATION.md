# Installation Guide

This guide provides comprehensive installation instructions for py10x, including all prerequisites and setup steps for different use cases.

## Prerequisites

### Core Requirements

- **Python 3.12 (recommended), 3.10+ supported** - Install via UV for best experience
- **[UV](https://docs.astral.sh/uv/)** - Python installer and package manager (recommended)
- **Git** - For cloning the repository

### Build Dependencies

- **C++ Compiler with C++20 support**
  - **Linux**: GCC 10+ or Clang 10+
  - **macOS**: Xcode Command Line Tools (Clang) or GCC 10+
  - **Windows**: MSVC 2022+ (Visual Studio 2022) or MinGW-w64 with GCC 10+
  - Required for building `cxx10x` dependencies which are distributed as source code

### Optional UI Dependencies

- **Node.js and npm** (for Rio UI backend)
  - Required if you plan to use Rio UI components
  - Download from [nodejs.org](https://nodejs.org/)

### Optional Database Dependencies

- **MongoDB** (for running tests and examples)
  - Required for running tests and examples that use MongoDB storage
  - Local passwordless MongoDB instance on default port 27017

## Installation Methods

### Install UV and Python

First, install UV (which includes Python installation):

#### Linux/macOS
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add UV to PATH (add to your shell profile)
export PATH="$HOME/.cargo/bin:$PATH"

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

For developers who want to contribute to py10x or need all features:

```bash
# Clone the repository
git clone https://github.com/10X-LLC/py10x.git
cd py10x

# Install everything for development (recommended)
uv sync --all-extras

# Or install specific combinations
uv sync --extra dev --extra rio  # Development + Rio UI
uv sync --extra dev --extra qt   # Development + Qt6 UI

# Alternative with pip
pip install -e ".[dev,rio]"  # Development + Rio UI
pip install -e ".[dev,qt]"   # Development + Qt6 UI
```

### User Installation

For users who just want to use py10x:

```bash
# Install from PyPI (when available)
pip install py10x[rio]    # With Rio UI backend
pip install py10x[qt]     # With Qt6 UI backend
pip install py10x[rio,qt] # With both UI backends

# Or install from source
git clone https://github.com/10X-LLC/py10x.git
cd py10x
pip install .
```

## Platform-Specific Setup

### Linux

#### Ubuntu/Debian
```bash
# Install C++ compiler
sudo apt update
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
# Install C++ compiler
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
# Install Xcode Command Line Tools (includes Clang)
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

#### Using Chocolatey
```powershell
# Install Visual Studio Build Tools (includes MSVC)
choco install visualstudio2022buildtools
choco install visualstudio2022-workload-vctools

# Install MongoDB (for testing and examples) - optional
choco install mongodb

# Install Node.js (for Rio UI) - optional
choco install nodejs
```

#### Using WinGet
```powershell
# Install Visual Studio Build Tools
winget install Microsoft.VisualStudio.2022.BuildTools

# Install MongoDB (for testing and examples) - optional
winget install MongoDB.MongoDB

# Install Node.js (for Rio UI) - optional
winget install OpenJS.NodeJS
```

#### Manual Installation
1. Download and install [Visual Studio 2022](https://visualstudio.microsoft.com/downloads/) with C++ development workload
2. Download and install [MongoDB Community Server](https://www.mongodb.com/try/download/community) (for testing and examples) - optional
3. Download and install [Node.js](https://nodejs.org/) (for Rio UI) - optional

## Build System

py10x uses the `ux` build system abstraction layer that provides unified APIs across different UI backends (Rio and Qt6). The build system automatically:

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

# Check C++ compiler
g++ --version  # Linux/macOS
cl.exe         # Windows

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

- Check the [README.md](README.md) for overview and examples
- See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup
- Join our [Discord community](https://discord.gg/m7AQSXfFwf) for support
- Report issues on [GitHub](https://github.com/10X-LLC/py10x/issues)
