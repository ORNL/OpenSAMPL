# Installation

## User install

OpenSAMPL requires Python 3.10 or newer.

Install the published package with `pip`:

```bash
pip install opensampl
```

If you plan to use collection features such as remote NTP or Microchip collectors, install the optional collect dependencies:

```bash
pip install "opensampl[collect]"
```

If you want the packaged Docker-backed server tooling as well:

```bash
pip install "opensampl[server]"
```

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
