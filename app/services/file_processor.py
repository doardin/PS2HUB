"""File processor — identify, rename, and organize PS2 ISOs."""
import os
import re
import shutil

# PS2 serial pattern found in ISO binary (SYSTEM.CNF area)
_SERIAL_PATTERN = re.compile(rb'([A-Z]{4}_\d{3}\.\d{2})')

# Known PS2 serial prefixes
_PS2_PREFIXES = frozenset({
    'SLUS', 'SCUS',  # North America
    'SLES', 'SCES',  # Europe
    'SLPS', 'SCPS', 'SLPM',  # Japan
    'SLKA', 'SCKA',  # Korea
})

# CD games are typically under 700 MB
_CD_THRESHOLD = 700 * 1024 * 1024

# Valid ISO extensions
_VALID_EXTENSIONS = frozenset({'.iso', '.bin', '.img'})


def extract_serial(filepath, read_bytes=2 * 1024 * 1024):
    """Extract PS2 game serial from the first bytes of an ISO file.

    Scans the first 2 MB where SYSTEM.CNF and ELF headers reside.
    Returns serial in OPL format (e.g., 'SLUS_200.44') or None.
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read(read_bytes)

        # Find all potential serials and pick the first valid one
        for match in _SERIAL_PATTERN.finditer(data):
            serial = match.group(1).decode('ascii')
            prefix = serial[:4].upper()
            if prefix in _PS2_PREFIXES:
                return serial
    except (OSError, UnicodeDecodeError):
        pass

    return None


def determine_type(filepath):
    """Determine if a game is CD or DVD based on file size."""
    try:
        size = os.path.getsize(filepath)
        return 'CD' if size < _CD_THRESHOLD else 'DVD'
    except OSError:
        return 'DVD'


def is_valid_iso(filepath):
    """Check if a file looks like a valid PS2 ISO."""
    if not os.path.isfile(filepath):
        return False

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in _VALID_EXTENSIONS:
        return False

    # Minimum size check (a real PS2 game is at least a few MB)
    try:
        size = os.path.getsize(filepath)
        return size > 1024 * 1024  # > 1 MB
    except OSError:
        return False


def process_iso(filepath, dvd_dir, cd_dir, art_dir=None):
    """Process a downloaded/uploaded ISO file.

    Steps:
        1. Validate it looks like an ISO
        2. Extract PS2 serial from binary
        3. Determine CD vs DVD
        4. Rename to OPL format: SERIAL.Title.iso
        5. Move to the correct directory
        6. Download cover art if possible

    Args:
        filepath: Path to the ISO file to process.
        dvd_dir: Destination directory for DVD games.
        cd_dir: Destination directory for CD games.
        art_dir: Optional ART directory for cover art.

    Returns:
        Dict with processing results, or None on failure.
    """
    if not is_valid_iso(filepath):
        return None

    serial = extract_serial(filepath)
    game_type = determine_type(filepath)
    target_dir = dvd_dir if game_type == 'DVD' else cd_dir

    # Get original filename parts
    original_name = os.path.basename(filepath)
    name_without_ext, ext = os.path.splitext(original_name)
    ext = ext.lower()

    # Build OPL-compatible filename
    if serial:
        from flask import current_app
        from app.services.title_db import get_title

        real_title = None
        try:
            titles_dir = current_app.config.get('TITLES_DIR')
            if titles_dir:
                real_title = get_title(titles_dir, serial)
        except Exception as e:
            print(f"[FileProcessor] Error querying title DB: {e}")

        if real_title:
            # We found it in the DB! Clean it up for filename safety
            clean_name = re.sub(r'[<>:"/\\|?*]', '', real_title)
        else:
            # Fallback to original uploaded filename
            # Remove any existing serial pattern from the name
            clean_name = re.sub(
                r'^[A-Z]{4}[_-]\d{3}[._]\d{2}[._\s-]*',
                '', name_without_ext, flags=re.IGNORECASE
            ).strip(' ._-')

        if not clean_name:
            clean_name = 'Unknown Game'

        new_filename = f'{serial}.{clean_name}{ext}'
    else:
        # No serial found — keep original name
        new_filename = original_name

    target_path = os.path.join(target_dir, new_filename)

    # Avoid overwriting existing files
    if os.path.exists(target_path):
        base = os.path.splitext(new_filename)[0]
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(target_dir, f'{base} ({counter}){ext}')
            counter += 1

    # Move file
    os.makedirs(target_dir, exist_ok=True)
    shutil.move(filepath, target_path)

    # Download cover art in the background (best-effort)
    if serial and art_dir:
        try:
            from app.services.cover_art import download_cover
            download_cover(art_dir, serial)
        except Exception:
            pass  # Non-critical

    return {
        'serial': serial,
        'type': game_type,
        'filename': os.path.basename(target_path),
        'path': target_path,
        'original_name': original_name,
    }
