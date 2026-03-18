# Environment Setup

How to create virtual environments, install Python/Node, and set up Sophon on different operating systems.

## Version Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| **Python** | 3.11+ | Backend and skills |
| **Node.js** | 18+ (20 LTS recommended) | Frontend Vite/React |
| **npm** | 9+ | Bundled with Node |

---

## 1. Python Virtual Environment

### macOS / Linux

```bash
cd sophon

python3 -m venv .venv
source .venv/bin/activate

which python   # should point to .venv/bin/python
python --version  # 3.11+
```

### Windows (PowerShell)

```powershell
cd sophon

python -m venv .venv
.\.venv\Scripts\Activate.ps1

# If execution policy blocks: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

where python
python --version
```

### Windows (CMD)

```cmd
cd sophon
python -m venv .venv
.venv\Scripts\activate.bat
python --version
```

### If Python 3.11+ Is Not Installed

| Platform | Install |
|----------|---------|
| **macOS** | `brew install python@3.11` then `python3.11 -m venv .venv` |
| **Ubuntu/Debian** | `sudo apt install python3.11 python3.11-venv` |
| **Fedora** | `sudo dnf install python3.11` |
| **Windows** | Download from [python.org](https://www.python.org/downloads/), check "Add to PATH" |
| **Multi-version** | [pyenv](https://github.com/pyenv/pyenv): `pyenv install 3.11.9`, `pyenv local 3.11.9` |

---

## 2. Node.js Version

### nvm (recommended, cross-platform)

```bash
# Install nvm (macOS/Linux): https://github.com/nvm-sh/nvm#installing-and-updating
# Windows: nvm-windows https://github.com/coreybutler/nvm-windows

nvm install 20
nvm use 20

node -v   # v20.x.x
npm -v    # 10.x+
```

### System Install

| Platform | Command |
|----------|---------|
| **macOS** | `brew install node@20` |
| **Ubuntu** | `curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -` then `sudo apt install nodejs` |
| **Windows** | Download LTS from [nodejs.org](https://nodejs.org/) |
| **Fedora** | `sudo dnf install nodejs` (may be older; prefer nvm) |

### Project Node Version

`.nvmrc` in project root with `20`. Run `nvm use` in the project directory.

---

## 3. Full Setup by OS

### macOS

```bash
cd sophon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cd frontend && npm install && cd ..
cp .env.example .env
# Edit .env for LLM (DeepSeek / Qwen / Ollama)

python start.py              # Backend http://localhost:8080
# In another terminal:
cd frontend && npm run dev   # Frontend http://localhost:5173
```

### Linux (Ubuntu/Debian)

```bash
cd sophon
sudo apt update
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cd frontend && npm install && cd ..
cp .env.example .env
python start.py
```

### Windows

```powershell
cd sophon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium

cd frontend
npm install
cd ..
copy .env.example .env

python start.py
# New terminal: cd frontend; npm run dev
```

---

## 4. Optional: pyenv for Python

```bash
brew install pyenv
pyenv install 3.11.9
cd sophon
pyenv local 3.11.9
python -m venv .venv
source .venv/bin/activate
```

---

## 5. Troubleshooting

### Python: `python` not found

- **macOS/Linux**: Use `python3`
- **Windows**: Ensure "Add Python to PATH" was checked during install

### Node: `npm install` slow or fails

```bash
# Try an alternative registry
npm config set registry https://registry.npmmirror.com
# Or one-off: npm install --registry=https://registry.npmmirror.com
```

### Playwright: `playwright install chromium` fails

- **Linux**: Install system deps (see Ubuntu section above)
- **Permissions**: `playwright install chromium --with-deps` (may need sudo)
- **Proxy**: Set `PLAYWRIGHT_DOWNLOAD_HOST` if behind a proxy

### Venv activated but system Python still used

- **macOS/Linux**: `source .venv/bin/activate`
- **Windows PowerShell**: `.\.venv\Scripts\Activate.ps1`
- **Windows CMD**: `.venv\Scripts\activate.bat`

Prompt should show `(.venv)` when active.
