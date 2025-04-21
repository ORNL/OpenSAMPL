#!/usr/bin/env bash
# -*- coding: utf-8 -*-
cat << "EOF"

                        ____    _    __  __ ____  _     
  ___  _ __   ___ _ __ / ___|  / \  |  \/  |  _ \| |    
 / _ \| '_ \ / _ \ '_ \\___ \ / _ \ | |\/| | |_) | |    
| (_) | |_) |  __/ | | |___) / ___ \| |  | |  __/| |___ 
 \___/| .__/ \___|_| |_|____/_/   \_\_|  |_|_|   |_____|
      |_|
    tools for processing clock data

EOF

source .venv/bin/activate
source .env
uv build && uv publish --index "${UV_PUBLISH_INDEX}" --token "${UV_PUBLISH_TOKEN}"
rm -rf dist/