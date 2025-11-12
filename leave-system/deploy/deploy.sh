#!/bin/bash

# Michaelhouse Leave System - Deployment Script
# Deploys the system to production server

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================"
echo "Michaelhouse Leave System"
echo "Production Deployment"
echo -e "======================================${NC}\n"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo -e "${RED}Error: Do not run as root${NC}"
  echo "Run as regular user with sudo privileges"
  exit 1
fi

# Configuration
INSTALL_DIR="/opt/michaelhouse"
SERVICE_USER="michaelhouse"
VENV_DIR="$INSTALL_DIR/leave-system/venv"

echo -e "${YELLOW}[1/10] Checking prerequisites...${NC}"

# Check for required commands
for cmd in python3 psql pip3 systemctl; do
  if ! command -v $cmd &> /dev/null; then
    echo -e "${RED}Error: $cmd is not installed${NC}"
    exit 1
  fi
done

echo -e "${GREEN}✓ Prerequisites OK${NC}\n"

echo -e "${YELLOW}[2/10] Creating service user...${NC}"
if ! id "$SERVICE_USER" &>/dev/null; then
  sudo useradd -r -s /bin/bash -d "$INSTALL_DIR" "$SERVICE_USER"
  echo -e "${GREEN}✓ User created${NC}"
else
  echo -e "${GREEN}✓ User exists${NC}"
fi
echo

echo -e "${YELLOW}[3/10] Creating installation directory...${NC}"
sudo mkdir -p "$INSTALL_DIR"
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
echo -e "${GREEN}✓ Directory created${NC}\n"

echo -e "${YELLOW}[4/10] Copying application files...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sudo -u "$SERVICE_USER" cp -r "$SCRIPT_DIR" "$INSTALL_DIR/"
echo -e "${GREEN}✓ Files copied${NC}\n"

echo -e "${YELLOW}[5/10] Setting up Python virtual environment...${NC}"
sudo -u "$SERVICE_USER" python3 -m venv "$VENV_DIR"
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/leave-system/requirements.txt"
echo -e "${GREEN}✓ Virtual environment created${NC}\n"

echo -e "${YELLOW}[6/10] Setting up database...${NC}"
cd "$INSTALL_DIR/leave-system/database"
sudo -u "$SERVICE_USER" ./setup_database.sh
echo -e "${GREEN}✓ Database configured${NC}\n"

echo -e "${YELLOW}[7/10] Configuring environment...${NC}"
if [ ! -f "$INSTALL_DIR/leave-system/.env" ]; then
  echo -e "${YELLOW}Creating .env file...${NC}"
  sudo -u "$SERVICE_USER" bash -c "cat > '$INSTALL_DIR/leave-system/.env' <<EOF
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=michaelhouse_leave
DB_USER=leave_user
DB_PASSWORD=CHANGE_THIS_PASSWORD

# Flask Configuration
FLASK_ENV=production
FLASK_PORT=8090

# Email Configuration
LEAVE_EMAIL=leave@michaelhouse.org
LEAVE_EMAIL_PASSWORD=CHANGE_THIS_PASSWORD
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com

# WhatsApp Bridge
WHATSAPP_BRIDGE_URL=http://localhost:8080
EOF"
  echo -e "${YELLOW}⚠ Please edit $INSTALL_DIR/leave-system/.env with correct passwords${NC}"
else
  echo -e "${GREEN}✓ .env file exists${NC}"
fi
echo

echo -e "${YELLOW}[8/10] Installing systemd services...${NC}"
sudo cp "$INSTALL_DIR/leave-system/deploy/leave-api.service" /etc/systemd/system/
sudo cp "$INSTALL_DIR/leave-system/email-bridge/email-service.service" /etc/systemd/system/
sudo systemctl daemon-reload
echo -e "${GREEN}✓ Services installed${NC}\n"

echo -e "${YELLOW}[9/10] Creating log directory...${NC}"
sudo mkdir -p /var/log/leave-system
sudo chown "$SERVICE_USER:$SERVICE_USER" /var/log/leave-system
echo -e "${GREEN}✓ Logs configured${NC}\n"

echo -e "${YELLOW}[10/10] Setting permissions...${NC}"
sudo chmod +x "$INSTALL_DIR/leave-system/database/setup_database.sh"
sudo chmod +x "$INSTALL_DIR/leave-system/api_production.py"
sudo chmod +x "$INSTALL_DIR/leave-system/email-bridge/email_service.py"
echo -e "${GREEN}✓ Permissions set${NC}\n"

echo -e "${GREEN}======================================"
echo "Deployment Complete!"
echo -e "======================================${NC}\n"

echo "Next steps:"
echo "1. Edit configuration:"
echo "   sudo nano $INSTALL_DIR/leave-system/.env"
echo
echo "2. Enable services:"
echo "   sudo systemctl enable leave-api"
echo "   sudo systemctl enable email-service"
echo
echo "3. Start services:"
echo "   sudo systemctl start leave-api"
echo "   sudo systemctl start email-service"
echo
echo "4. Check status:"
echo "   sudo systemctl status leave-api"
echo "   sudo systemctl status email-service"
echo
echo "5. View logs:"
echo "   sudo journalctl -u leave-api -f"
echo "   sudo journalctl -u email-service -f"
echo
