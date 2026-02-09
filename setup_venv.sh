#!/bin/bash

# Define the virtual environment directory
VENV_DIR="venv"

# Check if python3.12 exists, otherwise fall back to python3
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
else
    echo "Python 3.12 not found, using python3..."
    PYTHON_CMD="python3"
fi

# Create virtual environment
echo "Creating virtual environment in $VENV_DIR..."
$PYTHON_CMD -m venv $VENV_DIR

# Activate virtual environment
source $VENV_DIR/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "requirements.txt not found!"
fi

echo "Setup complete. To activate the virtual environment, run:"
echo "source $VENV_DIR/bin/activate"
