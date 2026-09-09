"""Cover art service — fetch and serve PS2 game cover art."""
import os
import re
import requests

# URL pattern for the xlenore/ps2-covers GitHub repository
_COVERS_URL = 'https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/{serial}.jpg'

# OPL cover filename pattern: SLUS_200.44_COV.jpg
_COVER_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp')


def find_cover(art_dir, serial):
    """Find existing cover art for a game serial in the ART directory.

    OPL convention: SLUS_200.44_COV.jpg

    Returns the full path if found, None otherwise.
    """
    if not serial or not os.path.isdir(art_dir):
        return None

    base = f'{serial}_COV'
    for ext in _COVER_EXTENSIONS:
        path = os.path.join(art_dir, base + ext)
        if os.path.isfile(path):
            return path

    return None


def serial_to_github_format(serial):
    """Convert OPL serial format to GitHub covers format.

    OPL:    SLUS_200.44
    GitHub: SLUS-20044
    """
    if not serial:
        return None

    # SLUS_200.44 → SLUS-20044
    match = re.match(r'^([A-Z]{4})_(\d{3})\.(\d{2})$', serial, re.IGNORECASE)
    if match:
        return f'{match.group(1).upper()}-{match.group(2)}{match.group(3)}'

    return serial


def download_cover(art_dir, serial, timeout=10):
    """Download cover art from the ps2-covers GitHub repository.

    Saves as OPL-compatible filename: {serial}_COV.jpg
    Returns the saved path on success, None on failure.
    """
    if not serial:
        return None

    os.makedirs(art_dir, exist_ok=True)

    # Check if already exists
    existing = find_cover(art_dir, serial)
    if existing:
        return existing

    github_serial = serial_to_github_format(serial)
    if not github_serial:
        return None

    url = _COVERS_URL.format(serial=github_serial)

    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and len(resp.content) > 1000:
            save_path = os.path.join(art_dir, f'{serial}_COV.jpg')
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            return save_path
    except (requests.RequestException, OSError):
        pass

    return None
