#!/usr/bin/env bash
# deploy.sh — Full VPS deployment for Geo-Crop Collector
# Run once on a fresh Ubuntu 22.04+ server as root (then re-run for updates)
# Usage: sudo bash scripts/deploy.sh
set -euo pipefail

PROJECT_DIR=/var/www/geocrop
VENV_DIR=$PROJECT_DIR/venv
DOMAIN=${DOMAIN:-yourdomain.com}
DB_NAME=geocrop
DB_USER=geocrop

echo "═══════════════════════════════════════════"
echo " Geo-Crop Collector — VPS Deploy"
echo "═══════════════════════════════════════════"

# ── 1. System packages ─────────────────────────────────────────────────────────
echo "▶ Installing system packages…"
apt-get update -q
apt-get install -y -q \
    python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib \
    postgis postgresql-15-postgis-3 \
    gdal-bin libgdal-dev \
    nginx certbot python3-certbot-nginx \
    git curl build-essential

# ── 2. PostgreSQL + PostGIS ────────────────────────────────────────────────────
echo "▶ Setting up PostgreSQL + PostGIS…"
systemctl enable --now postgresql

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;"
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$(openssl rand -base64 24)';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis;"
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis_topology;"

# ── 3. App directory ────────────────────────────────────────────────────────────
echo "▶ Setting up app directory…"
mkdir -p $PROJECT_DIR/backend/media/mbtiles
mkdir -p $PROJECT_DIR/backend/media/field_photos
mkdir -p $PROJECT_DIR/frontend/dist
mkdir -p /var/log/geocrop
chown -R www-data:www-data $PROJECT_DIR /var/log/geocrop

# Copy project files (assumes you've rsync'd or git pull'd already)
# git clone https://github.com/yourorg/geo-crop-collector.git $PROJECT_DIR
# or: rsync -avz --exclude='.git' ./ $PROJECT_DIR/

# ── 4. Python virtualenv ────────────────────────────────────────────────────────
echo "▶ Creating Python virtualenv…"
python3 -m venv $VENV_DIR
$VENV_DIR/bin/pip install --upgrade pip -q
$VENV_DIR/bin/pip install -r $PROJECT_DIR/backend/requirements.txt -q

# ── 4b. Adaptive capacity — detect hardware, write limits to .env ──────────────
echo "▶ Computing adaptive capacity settings…"
sed -i '/^\(GUNICORN_WORKERS\|GUNICORN_TIMEOUT\|PAGE_SIZE\|GEOJSON_MAX_FEATURES\|EXPORT_MAX_ROWS\|SYNC_PULL_MAX_ROWS\|MBTILES_CACHE_SIZE\|MBTILES_MAX_SIZE_MB\|ITERATOR_CHUNK_SIZE\|THROTTLE_ANON\|THROTTLE_USER\|DB_MAX_CONNECTIONS\|NGINX_RATE_PER_SEC\|NGINX_BURST\|PG_MAX_CONNECTIONS\|PG_SHARED_BUFFERS_MB\|PG_EFFECTIVE_CACHE_SIZE_MB\|PG_WORK_MEM_MB\|PG_MAINTENANCE_WORK_MEM_MB\|PG_WAL_BUFFERS_MB\|CAPACITY_RAM_MB\|CAPACITY_CPU_CORES\|CAPACITY_FREE_DISK_MB\)=/d' \
    $PROJECT_DIR/backend/.env 2>/dev/null || true
$VENV_DIR/bin/python $PROJECT_DIR/backend/geo_crop/capacity.py >> $PROJECT_DIR/backend/.env
echo "  RAM:     $(grep '^CAPACITY_RAM_MB='    $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2) MB"
echo "  CPUs:    $(grep '^CAPACITY_CPU_CORES=' $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)"
echo "  Workers: $(grep '^GUNICORN_WORKERS='   $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)"

# ── 4c. Configure PostgreSQL from computed PG_* values ────────────────────────
# Set SKIP_PG_CONFIGURE=true in .env to manage postgresql.conf manually.
if grep -q '^SKIP_PG_CONFIGURE=true' $PROJECT_DIR/backend/.env 2>/dev/null; then
    echo "  Skipping PostgreSQL configuration (SKIP_PG_CONFIGURE=true)"
else
    PG_MAX_CONN=$(grep '^PG_MAX_CONNECTIONS='        $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
    PG_SHB=$(    grep '^PG_SHARED_BUFFERS_MB='       $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
    PG_ECS=$(    grep '^PG_EFFECTIVE_CACHE_SIZE_MB=' $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
    PG_WM=$(     grep '^PG_WORK_MEM_MB='             $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
    PG_MWM=$(    grep '^PG_MAINTENANCE_WORK_MEM_MB=' $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
    PG_WAL=$(    grep '^PG_WAL_BUFFERS_MB='          $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)

    echo "▶ Configuring PostgreSQL: max_connections=$PG_MAX_CONN, shared_buffers=${PG_SHB}MB…"
    sudo -u postgres psql -c "ALTER SYSTEM SET max_connections             = $PG_MAX_CONN;"
    sudo -u postgres psql -c "ALTER SYSTEM SET shared_buffers             = '${PG_SHB}MB';"
    sudo -u postgres psql -c "ALTER SYSTEM SET effective_cache_size       = '${PG_ECS}MB';"
    sudo -u postgres psql -c "ALTER SYSTEM SET work_mem                   = '${PG_WM}MB';"
    sudo -u postgres psql -c "ALTER SYSTEM SET maintenance_work_mem       = '${PG_MWM}MB';"
    sudo -u postgres psql -c "ALTER SYSTEM SET wal_buffers                = '${PG_WAL}MB';"
    sudo systemctl restart postgresql
    echo "  PostgreSQL restarted with adaptive settings."
fi

# ── 5. Django setup ─────────────────────────────────────────────────────────────
echo "▶ Running Django migrations…"
cd $PROJECT_DIR/backend
$VENV_DIR/bin/python manage.py migrate --noinput
$VENV_DIR/bin/python manage.py collectstatic --noinput

# ── 6. Systemd service ──────────────────────────────────────────────────────────
echo "▶ Installing systemd service…"
cp $PROJECT_DIR/scripts/geocrop.service /etc/systemd/system/geocrop.service
sed -i "s|/var/www/geocrop|$PROJECT_DIR|g" /etc/systemd/system/geocrop.service
systemctl daemon-reload
systemctl enable geocrop
systemctl restart geocrop

# ── 7. Nginx ────────────────────────────────────────────────────────────────────
echo "▶ Configuring Nginx…"
cp $PROJECT_DIR/nginx/geocrop.conf /etc/nginx/sites-available/geocrop
sed -i "s/yourdomain.com/$DOMAIN/g" /etc/nginx/sites-available/geocrop
sed -i "s|/var/www/geocrop|$PROJECT_DIR|g" /etc/nginx/sites-available/geocrop

# Patch adaptive rate limit values from capacity.py output
NGINX_RATE=$(grep '^NGINX_RATE_PER_SEC=' $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
NGINX_BRST=$(grep '^NGINX_BURST='        $PROJECT_DIR/backend/.env | tail -1 | cut -d= -f2)
sed -i "s/rate=[0-9]*r\/s/rate=${NGINX_RATE}r\/s/" /etc/nginx/sites-available/geocrop
sed -i "s/burst=[0-9]* nodelay/burst=${NGINX_BRST} nodelay/" /etc/nginx/sites-available/geocrop
echo "  Nginx rate limit: ${NGINX_RATE}r/s burst=${NGINX_BRST}"
ln -sf /etc/nginx/sites-available/geocrop /etc/nginx/sites-enabled/geocrop
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 8. TLS — Let's Encrypt ──────────────────────────────────────────────────────
echo "▶ Obtaining TLS certificate…"
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos \
    -m admin@$DOMAIN --redirect || echo "⚠ certbot failed — run manually"

# ── 9. JWT blacklist cleanup cron ─────────────────────────────────────────────
echo "▶ Installing JWT cleanup cron…"
CRON_JWT="0 3 * * * $VENV_DIR/bin/python $PROJECT_DIR/backend/manage.py flushexpiredtokens >> /var/log/geocrop/cron.log 2>&1"
( crontab -l 2>/dev/null | grep -qF 'flushexpiredtokens' ) || \
    ( crontab -l 2>/dev/null; echo "$CRON_JWT" ) | crontab -

echo ""
echo "✅ Deployment complete!"
echo "   API:   https://$DOMAIN/api/"
echo "   Admin: https://$DOMAIN/admin/"
echo ""
echo "Next steps:"
echo "  1. Edit $PROJECT_DIR/backend/.env with your secrets"
echo "  2. Run: python manage.py createsuperuser"
echo "  3. Deploy your frontend files to $PROJECT_DIR/frontend/dist/"
