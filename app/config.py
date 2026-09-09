"""Centralized configuration. Override via environment variables."""
import os


class Config:
    """Application configuration.

    All paths are derived from PS2_ROOT so the project is portable.
    Set PS2_ROOT env var to change the data directory.
    """

    # ── Base directory ──────────────────────────────────────────────
    PS2_ROOT = os.environ.get('PS2_ROOT', '/srv/ps2')

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
