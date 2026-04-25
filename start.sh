#!/bin/bash

# PhishGuard Launcher Script
# This script automates the setup and execution of the PhishGuard platform.

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛡 PhishGuard Launcher${NC}"
echo "----------------------"

# 1. Check for Virtual Environment
if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment 'venv' not found.${NC}"
    echo "Creating venv..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment. Please install python3-venv."
        exit 1
    fi
fi

# 2. Activate Venv
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# 3. Ensure pip is installed (bootstrap if missing)
if ! command -v pip &> /dev/null; then
    echo "Pip not found in venv. Bootstrapping..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
fi

# 4. Install/Update Dependencies
echo -e "${GREEN}Checking dependencies...${NC}"
pip install -r requirements.txt --quiet

# 5. Check Docker (Optional)
if command -v docker-compose &> /dev/null; then
    echo -e "${BLUE}Starting Docker services (Redis, Mailhog)...${NC}"
    docker-compose up -d redis mailhog
else
    echo -e "${RED}Docker Compose not found. Proceeding with in-memory fallbacks.${NC}"
fi

# 6. Set Environment Variables (Defaults if .env is missing)
if [ ! -f ".env" ]; then
    echo "Creating default .env file..."
    cat > .env <<EOL
DATABASE_URL=sqlite:///./phishguard.db
REDIS_URL=redis://localhost:6379/0
SMTP_HOST=localhost
SMTP_PORT=1025
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
ANOMALY_THRESHOLD=17.53
SOFT_BAN_THRESHOLD=5
HARD_BAN_THRESHOLD=10
VICTIM_PC1_IP=192.168.1.101
VICTIM_PC2_IP=192.168.1.102
EOL
fi

# 7. Start the Server
echo -e "${GREEN}🚀 Starting PhishGuard Server...${NC}"
echo "Access the dashboards at:"
echo "⚔ Red Team: http://localhost:8000/attack/"
echo "🛡 Blue Team: http://localhost:8000/defense/"
echo "------------------------------------------"

# Use python -m backend.main to ensure proper path resolution
python3 -m backend.main
