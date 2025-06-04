#!/bin/bash

# Start both backend and frontend in separate terminals

echo "Starting O2FileSearchPlus..."

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if [[ "$OSTYPE" == "darwin"* ]]; then
    osascript <<APPLESCRIPT
        tell application "Terminal"
            do script "cd \"$(pwd)\" && ./start_backend.sh"
            do script "cd \"$(pwd)\" && ./start_frontend.sh"
        end tell
APPLESCRIPT
elif command_exists gnome-terminal; then
    gnome-terminal --tab --title="Backend" -- bash -c "./start_backend.sh; exec bash"
    gnome-terminal --tab --title="Frontend" -- bash -c "./start_frontend.sh; exec bash"
elif command_exists xterm; then
    xterm -title "Backend" -e "./start_backend.sh" &
    xterm -title "Frontend" -e "./start_frontend.sh" &
elif command_exists konsole; then
    konsole --new-tab -e "./start_backend.sh" &
    konsole --new-tab -e "./start_frontend.sh" &
else
    echo "No suitable terminal emulator found."
    echo "Please run the following commands in separate terminals:"
    echo "1. ./start_backend.sh"
    echo "2. ./start_frontend.sh"
fi

echo "Backend will be available at: http://localhost:8000"
echo "Frontend will be available at: http://localhost:3000"
echo "API Documentation at: http://localhost:8000/docs"
