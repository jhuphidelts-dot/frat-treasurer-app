#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the project directory
cd "$SCRIPT_DIR"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed or not in PATH"
    echo "Please install Python 3 to run this application"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if requirements are installed
if [ -f "requirements.txt" ]; then
    echo "Checking Python dependencies..."
    python3 -c "
import pkg_resources
import sys
try:
    with open('requirements.txt', 'r') as f:
        requirements = f.read().splitlines()
    pkg_resources.require(requirements)
    print('All dependencies are satisfied.')
except Exception as e:
    print('Missing dependencies detected.')
    print('Installing requirements...')
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
" 2>/dev/null
fi

echo ""
echo "🎓 Starting Fraternity Treasurer App..."
echo "📊 Dashboard will be available at: http://127.0.0.1:8080"
echo "👤 Default login: admin / admin123"
echo ""
echo "🛑 Press Ctrl+C to stop the server"
echo "📱 You can now open http://127.0.0.1:8080 in your browser"
echo ""

# Start the application
python3 app.py

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Application failed to start. Check the error messages above."
    read -p "Press Enter to exit..."
fi
