#!/usr/bin/env bash
# generate documentation for opensampl module
set -e  # fail immediately on error
# ensure all dependencies are installed
uv sync
source .venv/bin/activate
# run the auto documentation generator
python ./scripts/gen_api_docs.py
# build the documentation (clean slate)
mkdocs build --clean