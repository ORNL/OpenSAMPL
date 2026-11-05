# Installation

## User install

OpenSAMPL requires Python 3.11–3.14.

Install the published package with `pip`:

```bash
pip install opensampl
```

If you plan to use collection features such as remote NTP or Microchip collectors, install the optional collect dependencies:

```bash
pip install "opensampl[collect]"
```

The base package includes the Docker-backed server launcher. Install Docker Engine and Docker Compose separately to use `opensampl-server`. The `backend` and `migrations` extras are needed only when running those Python services outside their containers.

## Developer Installation

The repository uses `uv` for local development workflows.

```bash
git clone git@github.com:ORNL/OpenSAMPL.git
cd OpenSAMPL
uv venv
uv sync --all-extras --dev
source .venv/bin/activate
```

That installs:

- the package into the local virtual environment
- all optional extras
- development tools such as `pytest`, `ruff`, and `mkdocs`
