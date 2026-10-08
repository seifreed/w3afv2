#!/bin/bash -x

# Install the GUI dependencies
python -c 'from w3af.core.ui.gui.dependency_check.dependency_check import dependency_check;dependency_check()'

if [ -f requirements.txt ]; then
    python -m pip install -r requirements.txt
fi
