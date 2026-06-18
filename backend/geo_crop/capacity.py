"""
Detects host CPU, RAM, and disk; derives safe operating limits AND PostgreSQL config.
No Django imports — usable from deploy scripts.

  python backend/geo_crop/capacity.py >> backend/.env
"""
import os
import shutil


def _detect_ram_mb() -> int:
    try:
        return max(1, (os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')) // (1024 * 1024))
    except (AttributeError, ValueError, OSError):
        return 512  # conservative fallback — smallest safe caps


def _detect_cpu_cores() -> int:
    return max(1, os.cpu_count() or 1)


def _detect_free_disk_mb() -> int:
    try:
        return max(1, shutil.disk_usage('/').free // (1024 * 1024))
    except OSError:
        return 10_240  # 10 GB fallback


RAM_MB       : int = _detect_ram_mb()
CPU_CORES    : int = _detect_cpu_cores()
FREE_DISK_MB : int = _detect_free_disk_mb()

# ── PostgreSQL settings — computed from RAM, emitted for deploy.sh to apply ───

# shared_buffers = 25% of RAM (PostgreSQL's primary cache — most impactful setting)
PG_SHARED_BUFFERS_MB      : int = max(128, RAM_MB // 4)

# effective_cache_size = 75% of RAM (planner hint only, no actual allocation)
PG_EFFECTIVE_CACHE_SIZE_MB: int = max(256, (RAM_MB * 3) // 4)

# max_connections = ~1 connection per 8 MB RAM
# Each connection slot pre-allocates lock table entries: 64 locks × conn × 272 bytes
PG_MAX_CONNECTIONS        : int = max(100, RAM_MB // 8)

# work_mem = 25% of RAM split across expected concurrent sort operations
PG_WORK_MEM_MB            : int = max(4, (RAM_MB // 4) // max(1, PG_MAX_CONNECTIONS // 10))

# maintenance_work_mem = 6% of RAM (VACUUM, CREATE INDEX, etc.)
PG_MAINTENANCE_WORK_MEM_MB: int = max(64, RAM_MB // 16)

# wal_buffers = 3% of shared_buffers, capped at 64 MB
PG_WAL_BUFFERS_MB         : int = max(16, min(64, PG_SHARED_BUFFERS_MB * 3 // 100))

# ── Application limits — formula-based, no upper ceiling ──────────────────────

# Each GeoJSON feature ≈ 2 KB. Allow 1% of RAM for one GeoJSON response.
# RAM_MB * 5  ≈  (RAM_MB * 1024 * 1024 * 0.01) / 2048
GEOJSON_MAX_FEATURES: int = max(2_000, RAM_MB * 5)
EXPORT_MAX_ROWS      : int = max(4_000, RAM_MB * 10)   # 2% of RAM
SYNC_PULL_MAX_ROWS   : int = max(2_000, RAM_MB * 5)

# Each tile cache slot ≈ 10 KB. Allow 0.25% of RAM to the tile cache.
MBTILES_CACHE_SIZE: int = max(256, RAM_MB // 4)

# MBTiles upload cap = 10% of free disk, capped at 50 GB, minimum 100 MB
MBTILES_MAX_SIZE_MB: int = max(100, min(51_200, FREE_DISK_MB // 10))

# DRF page size — how many records per paginated list response
# Scales with RAM: larger server can afford to serialize more per page
PAGE_SIZE: int = max(20, min(500, RAM_MB // 20))

# Gunicorn request timeout — scales with RAM (more RAM = bigger files = longer ops)
# Minimum 60s, maximum 600s
GUNICORN_TIMEOUT: int = max(60, min(600, RAM_MB // 10))

# Nginx rate limit and burst — scale with worker count
# Each worker handles ~10 r/s sustained; burst = 2× sustained per worker
NGINX_RATE_PER_SEC: int = 0  # computed after GUNICORN_WORKERS is set
NGINX_BURST       : int = 0  # computed after GUNICORN_WORKERS is set

# DB iterator chunk size — scales with RAM for fewer DB round-trips
ITERATOR_CHUNK_SIZE: int = max(500, min(5_000, RAM_MB // 20))

# Workers: bounded by CPU headroom, RAM headroom, and DB connection headroom.
# Each Gunicorn sync worker uses ~100 MB RAM.
# DB_MAX_CONNECTIONS env var is written by this script on previous deploy; on first
# run it falls back to PG_MAX_CONNECTIONS computed above.
_DB_MAX_CONN   : int = int(os.environ.get('DB_MAX_CONNECTIONS', PG_MAX_CONNECTIONS))
_by_cpu        : int = 2 * CPU_CORES + 1
_by_ram        : int = max(1, RAM_MB // 100)
_by_db         : int = max(1, int(_DB_MAX_CONN * 0.8))
GUNICORN_WORKERS: int = min(_by_cpu, _by_ram, _by_db)

# Throttle rates scale with worker count.
THROTTLE_ANON: str = f"{GUNICORN_WORKERS * 20}/min"
THROTTLE_USER: str = f"{GUNICORN_WORKERS * 100}/min"

# Nginx rate limit — compute now that GUNICORN_WORKERS is known
NGINX_RATE_PER_SEC = max(10, GUNICORN_WORKERS * 10)
NGINX_BURST        = GUNICORN_WORKERS * 20

if __name__ == '__main__':
    for key, val in [
        # Django / Gunicorn
        ('GUNICORN_WORKERS',           GUNICORN_WORKERS),
        ('GUNICORN_TIMEOUT',           GUNICORN_TIMEOUT),
        ('PAGE_SIZE',                  PAGE_SIZE),
        ('GEOJSON_MAX_FEATURES',       GEOJSON_MAX_FEATURES),
        ('EXPORT_MAX_ROWS',            EXPORT_MAX_ROWS),
        ('SYNC_PULL_MAX_ROWS',         SYNC_PULL_MAX_ROWS),
        ('MBTILES_CACHE_SIZE',         MBTILES_CACHE_SIZE),
        ('MBTILES_MAX_SIZE_MB',        MBTILES_MAX_SIZE_MB),
        ('ITERATOR_CHUNK_SIZE',        ITERATOR_CHUNK_SIZE),
        ('THROTTLE_ANON',              THROTTLE_ANON),
        ('THROTTLE_USER',              THROTTLE_USER),
        ('DB_MAX_CONNECTIONS',         PG_MAX_CONNECTIONS),   # mirrors PG value
        # Nginx (consumed by deploy.sh to patch geocrop.conf)
        ('NGINX_RATE_PER_SEC',         NGINX_RATE_PER_SEC),
        ('NGINX_BURST',                NGINX_BURST),
        # PostgreSQL (consumed by deploy.sh, not by Django)
        ('PG_MAX_CONNECTIONS',         PG_MAX_CONNECTIONS),
        ('PG_SHARED_BUFFERS_MB',       PG_SHARED_BUFFERS_MB),
        ('PG_EFFECTIVE_CACHE_SIZE_MB', PG_EFFECTIVE_CACHE_SIZE_MB),
        ('PG_WORK_MEM_MB',             PG_WORK_MEM_MB),
        ('PG_MAINTENANCE_WORK_MEM_MB', PG_MAINTENANCE_WORK_MEM_MB),
        ('PG_WAL_BUFFERS_MB',          PG_WAL_BUFFERS_MB),
        # Informational
        ('CAPACITY_RAM_MB',            RAM_MB),
        ('CAPACITY_CPU_CORES',         CPU_CORES),
        ('CAPACITY_FREE_DISK_MB',      FREE_DISK_MB),
    ]:
        print(f'{key}={val}')
