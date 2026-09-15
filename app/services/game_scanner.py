"""Game scanner service — reads DVD/ and CD/ directories for PS2 ISOs."""
import os
import re
import shutil

# OPL naming pattern: SLUS_123.45.Game Name.iso
_OPL_PATTERN = re.compile(
    r'^([A-Z]{4}_\d{3}\.\d{2})\.(.+)\.(iso|bin|img)$',
    re.IGNORECASE,
)


def scan_games(dvd_dir, cd_dir):
    """Scan DVD and CD directories for PS2 game files.

    Returns a sorted list of game dicts with: id, serial, title,
    filename, size, size_human, type (DVD/CD).
    """
    games = []

    for game_type, directory in [('DVD', dvd_dir), ('CD', cd_dir)]:
        if not os.path.isdir(directory):
            continue

        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in ('.iso', '.bin', '.img'):
                continue

            size = os.path.getsize(filepath)
            match = _OPL_PATTERN.match(filename)

            if match:
                serial = match.group(1)
                title = match.group(2)
            else:
                # Non-OPL filename: use full name without extension
                serial = None
                title = os.path.splitext(filename)[0]

            games.append({
                'id': serial or filename,
                'serial': serial,
                'title': title,
                'filename': filename,
                'size': size,
                'size_human': _format_size(size),
                'type': game_type,
            })

    games.sort(key=lambda g: g['title'].lower())
    return games


def get_disk_usage(path):
    """Return disk usage stats for the partition containing `path`.

    Returns a dict with total, used, free (bytes + human-readable),
    or None on error.
    """
    try:
        usage = shutil.disk_usage(path)
        return {
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'total_human': _format_size(usage.total),
            'used_human': _format_size(usage.used),
            'free_human': _format_size(usage.free),
        }
    except OSError:
        return None


def _format_size(size_bytes):
    """Format byte count to human-readable string."""
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 ** 2:
        return f'{size_bytes / 1024:.2f} KB'
    elif size_bytes < 1024 ** 3:
        return f'{size_bytes / 1024 ** 2:.2f} MB'
    else:
        return f'{size_bytes / 1024 ** 3:.2f} GB'
