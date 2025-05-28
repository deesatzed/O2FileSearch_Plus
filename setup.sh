#!/bin/bash

# O2FileSearchPlus Enhanced Setup Script
# This script sets up both backend and frontend components

set -e  # Exit on any error

echo "🚀 O2FileSearchPlus Enhanced Setup"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_warning "This script is designed for Linux. Some features may not work on other systems."
fi

# Check for required commands
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

print_status "Checking prerequisites..."

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Python 3.8+ is required. Found: $(python3 --version)"
        exit 1
    fi
    print_success "Python $(python3 --version | cut -d' ' -f2) found"
else
    print_error "Python 3 is not installed"
    exit 1
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        print_error "Node.js 18+ is required. Found: $(node --version)"
        exit 1
    fi
    print_success "Node.js $(node --version) found"
else
    print_error "Node.js is not installed"
    exit 1
fi

# Check npm
check_command npm
print_success "npm $(npm --version) found"

# Setup Backend
print_status "Setting up backend..."

cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt
print_success "Backend dependencies installed"

# Test backend import
print_status "Testing backend setup..."
python -c "import fastapi, uvicorn, chardet; print('Backend dependencies OK')" || {
    print_error "Backend dependency test failed"
    exit 1
}
print_success "Backend setup complete"

# Go back to root directory
cd ..

# Setup Frontend
print_status "Setting up frontend..."

cd frontend

# Install Node.js dependencies
print_status "Installing Node.js dependencies..."
npm install
print_success "Frontend dependencies installed"

# Test frontend build
print_status "Testing frontend build..."
npm run build || {
    print_error "Frontend build test failed"
    exit 1
}
print_success "Frontend setup complete"

# Go back to root directory
cd ..

# Create startup scripts
print_status "Creating startup scripts..."

# Backend startup script
cat > start_backend.sh << 'EOF'
#!/bin/bash
cd backend
source venv/bin/activate
echo "Starting O2FileSearchPlus Backend on http://localhost:8000"
echo "API Documentation available at http://localhost:8000/docs"
python main.py
EOF

# Frontend startup script
cat > start_frontend.sh << 'EOF'
#!/bin/bash
cd frontend
echo "Starting O2FileSearchPlus Frontend on http://localhost:3000"
npm run dev
EOF

# Combined startup script
cat > start_all.sh << 'EOF'
#!/bin/bash

# Start both backend and frontend in separate terminals
echo "Starting O2FileSearchPlus Enhanced..."

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Try to open in separate terminals
if command_exists gnome-terminal; then
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
EOF

# Make scripts executable
chmod +x start_backend.sh start_frontend.sh start_all.sh

print_success "Startup scripts created"

# Create systemd service file template
print_status "Creating systemd service template..."

cat > o2filesearch.service << EOF
[Unit]
Description=O2FileSearchPlus Enhanced Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/backend
Environment=PATH=$(pwd)/backend/venv/bin
ExecStart=$(pwd)/backend/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd service template created"

# Final instructions
echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Quick Start:"
echo "1. Run: ./start_all.sh"
echo "2. Open http://localhost:3000 in your browser"
echo "3. Go to Index tab and start indexing your files"
echo ""
echo "Manual Start:"
echo "1. Backend: ./start_backend.sh"
echo "2. Frontend: ./start_frontend.sh"
echo ""
echo "Production Deployment:"
echo "1. Copy o2filesearch.service to /etc/systemd/system/"
echo "2. Run: sudo systemctl enable o2filesearch"
echo "3. Run: sudo systemctl start o2filesearch"
echo "4. Build frontend: cd frontend && npm run build && npm start"
echo ""
echo "Troubleshooting:"
echo "- Check logs in backend/o2filesearch.log"
echo "- Ensure ports 3000 and 8000 are available"
echo "- Verify file permissions for indexing directories"
echo ""
print_success "Ready to use O2FileSearchPlus Enhanced!"
