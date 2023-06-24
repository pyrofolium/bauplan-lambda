#!/usr/bin/env bash
pyenv install 3.10
pyenv global 3.10
python3.10 -m venv venv
set -e
source venv/bin/activate
python -m pip install -r requirements.txt

