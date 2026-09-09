"""Title Database service — downloads and parses PS2 serial-to-title mappings."""
import os
import json
import requests
import threading

_DB_URLS = [
    'https://raw.githubusercontent.com/garbled1/ps_ripper/master/db_playstation2_official_us.json',
    'https://raw.githubusercontent.com/garbled1/ps_ripper/master/db_playstation2_official_eu.json',
    'https://raw.githubusercontent.com/garbled1/ps_ripper/master/db_playstation2_official_jp.json'
]

_titles_cache = {}
_cache_lock = threading.Lock()
_loaded = False


def _ensure_db(titles_dir):
    """Download databases if they don't exist and load them into memory."""
    global _loaded
    if _loaded:
        return

    with _cache_lock:
        if _loaded:
            return

        os.makedirs(titles_dir, exist_ok=True)
        local_db_path = os.path.join(titles_dir, 'titles_master.json')

        # Load from disk if we already compiled it
        if os.path.exists(local_db_path):
            try:
                with open(local_db_path, 'r', encoding='utf-8') as f:
                    _titles_cache.update(json.load(f))
                _loaded = True
                return
            except Exception as e:
                print(f"[TitleDB] Error loading local DB: {e}")

        # Download and merge from sources
        print("[TitleDB] Downloading master title databases...")
        merged_db = {}
        for url in _DB_URLS:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    # Some serials might be formatted as SLUS-20000, normalize to SLUS_200.00
                    for raw_serial, title in data.items():
                        # We just keep it normalized without punctuation for easy lookup
                        norm_serial = raw_serial.replace('-', '').replace('_', '').replace('.', '').upper()
                        if norm_serial not in merged_db:
                            merged_db[norm_serial] = title
            except Exception as e:
                print(f"[TitleDB] Failed to download {url}: {e}")

        # Save to disk for future fast loads
        if merged_db:
            try:
                with open(local_db_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_db, f, indent=2)
            except Exception as e:
                print(f"[TitleDB] Failed to save local DB: {e}")

        _titles_cache.update(merged_db)
        _loaded = True


def get_title(titles_dir, serial):
    """Look up a title by serial. Returns None if not found.
    
    Serial can be SLUS_200.00 or SLUS20000, it will be normalized.
    """
    if not serial:
        return None

    _ensure_db(titles_dir)

    norm_serial = serial.replace('-', '').replace('_', '').replace('.', '').upper()
    return _titles_cache.get(norm_serial)
