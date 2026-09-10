"""Centralized configuration. Override via environment variables."""
import os


class Config:
    """Application configuration.

    All paths are derived from PS2_ROOT so the project is portable.
    Set PS2_ROOT env var to change the data directory.
    """

    # ── Base directory ──────────────────────────────────────────────
    # Default to /srv/ps2 on Linux, but fallback to local 'data' folder if not present
    _default_root = '/srv/ps2'
    if not os.path.exists('/srv/ps2'):
        _default_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

    PS2_ROOT = os.environ.get('PS2_ROOT', _default_root)

    # ── OPL directory structure ─────────────────────────────────────
    DVD_DIR = os.path.join(PS2_ROOT, 'DVD')
    CD_DIR = os.path.join(PS2_ROOT, 'CD')
    ART_DIR = os.path.join(PS2_ROOT, 'ART')
    CFG_DIR = os.path.join(PS2_ROOT, 'CFG')
    VMC_DIR = os.path.join(PS2_ROOT, 'VMC')
    DOWNLOADS_DIR = os.path.join(PS2_ROOT, 'downloads')

    # ── aria2 RPC ───────────────────────────────────────────────────
    ARIA2_RPC_URL = os.environ.get('ARIA2_RPC_URL', 'http://localhost:6800/jsonrpc')
    ARIA2_RPC_SECRET = os.environ.get('ARIA2_RPC_SECRET', 'ps2hub')

    # ── Upload & Metadata ───────────────────────────────────────────
    ALLOWED_EXTENSIONS = {'.iso', '.bin', '.img', '.zip', '.7z', '.rar'}
    MAX_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB para LAN
    TITLES_DIR = os.path.join(PS2_ROOT, 'titles')

    # ── Flask ───────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
