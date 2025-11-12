#!/bin/bash

# Michaelhouse Leave System - Database Setup Script
# Creates PostgreSQL database and loads schema + seed data

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================"
echo "Michaelhouse Leave System"
echo "Database Setup"
echo -e "======================================${NC}\n"

# Configuration
DB_NAME="${DB_NAME:-michaelhouse_leave}"
DB_USER="${DB_USER:-leave_user}"
DB_PASSWORD="${DB_PASSWORD:-secure_password_123}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL is not installed${NC}"
    echo "Install with: brew install postgresql (macOS) or apt-get install postgresql (Linux)"
    exit 1
fi

echo -e "${YELLOW}[1/6] Checking PostgreSQL connection...${NC}"
if ! psql -U "$POSTGRES_USER" -h "$DB_HOST" -p "$DB_PORT" -c '\q' 2>/dev/null; then
    echo -e "${RED}Error: Cannot connect to PostgreSQL${NC}"
    echo "Make sure PostgreSQL is running:"
    echo "  macOS: brew services start postgresql"
    echo "  Linux: sudo systemctl start postgresql"
    exit 1
fi
echo -e "${GREEN}✓ Connected to PostgreSQL${NC}\n"

# Drop existing database if requested
if [ "$1" == "--reset" ]; then
    echo -e "${YELLOW}[2/6] Dropping existing database (if exists)...${NC}"
    psql -U "$POSTGRES_USER" -h "$DB_HOST" -p "$DB_PORT" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    psql -U "$POSTGRES_USER" -h "$DB_HOST" -p "$DB_PORT" -c "DROP USER IF EXISTS $DB_USER;" 2>/dev/null || true
    echo -e "${GREEN}✓ Cleanup complete${NC}\n"
else
    echo -e "${YELLOW}[2/6] Skipping cleanup (use --reset to drop existing database)${NC}\n"
fi

# Create database user
echo -e "${YELLOW}[3/6] Creating database user...${NC}"
psql -U "$POSTGRES_USER" -h "$DB_HOST" -p "$DB_PORT" <<EOF
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;
EOF
echo -e "${GREEN}✓ User created/verified${NC}\n"

# Create database
echo -e "${YELLOW}[4/6] Creating database...${NC}"
psql -U "$POSTGRES_USER" -h "$DB_HOST" -p "$DB_PORT" <<EOF
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
EOF
echo -e "${GREEN}✓ Database created/verified${NC}\n"

# Load schema
echo -e "${YELLOW}[5/6] Loading database schema...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -f "$SCRIPT_DIR/schema.sql"
echo -e "${GREEN}✓ Schema loaded${NC}\n"

# Load seed data
echo -e "${YELLOW}[6/6] Loading seed data...${NC}"
psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -f "$SCRIPT_DIR/seed_data.sql"
echo -e "${GREEN}✓ Seed data loaded${NC}\n"

# Create .env file
echo -e "${YELLOW}Creating .env file...${NC}"
cat > "$SCRIPT_DIR/../.env" <<EOF
# Database Configuration
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# Application Configuration
FLASK_APP=api.py
FLASK_ENV=development
FLASK_PORT=8090

# Email Configuration (update these)
LEAVE_EMAIL=leave@michaelhouse.org
LEAVE_EMAIL_PASSWORD=your-app-specific-password
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com

# WhatsApp Bridge
WHATSAPP_BRIDGE_URL=http://localhost:8080
EOF
echo -e "${GREEN}✓ .env file created${NC}\n"

# Display connection info
echo -e "${GREEN}======================================"
echo "Setup Complete!"
echo -e "======================================${NC}\n"

echo "Database Connection Details:"
echo "  Host:     $DB_HOST"
echo "  Port:     $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "Connection String:"
echo "  postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Test connection:"
echo "  psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME"
echo ""
echo "Next Steps:"
echo "  1. Update .env file with email credentials"
echo "  2. Install Python dependencies: pip install -r requirements.txt"
echo "  3. Start Flask API: python3 api.py"
echo ""
