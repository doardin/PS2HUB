"""aria2 JSON-RPC client — manages downloads via aria2c daemon."""
import os
import requests as http_requests


class Aria2Error(Exception):
    """Raised when aria2 RPC returns an error or is unreachable."""
    pass


class Aria2Client:
    """Thin wrapper around the aria2 JSON-RPC interface."""

    def __init__(self, rpc_url, secret):
        self.rpc_url = rpc_url
        self.secret = secret
        self._id_counter = 0

    # ── Low-level RPC ───────────────────────────────────────────
    def _call(self, method, *params):
        """Make a JSON-RPC call to aria2."""
        self._id_counter += 1
        payload = {
            'jsonrpc': '2.0',
            'id': str(self._id_counter),
            'method': method,
            'params': [f'token:{self.secret}', *params],
        }
        try:
            resp = http_requests.post(self.rpc_url, json=payload, timeout=5)
            data = resp.json()
            if 'error' in data:
                raise Aria2Error(data['error'].get('message', 'Unknown error'))
            return data.get('result')
        except http_requests.ConnectionError:
            raise Aria2Error('Não foi possível conectar ao aria2. O serviço está rodando?')
        except http_requests.Timeout:
            raise Aria2Error('aria2 não respondeu a tempo.')
        except (ValueError, KeyError) as e:
            raise Aria2Error(f'Resposta inválida do aria2: {e}')

    def is_available(self):
        """Check if aria2 RPC is reachable."""
        try:
            self._call('aria2.getVersion')
            return True
        except Aria2Error:
            return False

    # ── Download management ─────────────────────────────────────
    _STATUS_KEYS = [
        'gid', 'status', 'totalLength', 'completedLength',
        'downloadSpeed', 'files', 'errorCode', 'errorMessage',
    ]

    def add_download(self, url, download_dir=None):
        """Add a new download by URL. Returns the GID."""
        opts = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'file-allocation': 'none'
        }
        if download_dir:
            opts['dir'] = download_dir
        return self._call('aria2.addUri', [url], opts)

    def get_status(self, gid):
        """Get status of a single download."""
        return self._call('aria2.tellStatus', gid, self._STATUS_KEYS)

    def list_active(self):
        """List currently downloading items."""
        return self._call('aria2.tellActive', self._STATUS_KEYS)

    def list_waiting(self, offset=0, num=50):
        """List queued downloads."""
        return self._call('aria2.tellWaiting', offset, num, self._STATUS_KEYS)

    def list_stopped(self, offset=0, num=20):
        """List completed/errored/removed downloads."""
        return self._call('aria2.tellStopped', offset, num, self._STATUS_KEYS)

    def list_all(self):
        """Return all downloads (active + waiting + stopped)."""
        active = self.list_active()
        waiting = self.list_waiting()
        stopped = self.list_stopped()
        return active + waiting + stopped

    def pause(self, gid):
        """Pause a download."""
        return self._call('aria2.pause', gid)

    def unpause(self, gid):
        """Resume a paused download."""
        return self._call('aria2.unpause', gid)

    def remove(self, gid):
        """Remove/cancel a download."""
        try:
            return self._call('aria2.remove', gid)
        except Aria2Error:
            # Already stopped — remove from results list
            return self._call('aria2.removeDownloadResult', gid)

    def purge_results(self):
        """Clear completed/error/removed download results."""
        return self._call('aria2.purgeDownloadResult')


# ── Formatting helpers ──────────────────────────────────────────

def format_download(raw):
    """Convert aria2 raw status dict to a clean, frontend-friendly dict."""
    files = raw.get('files', [])
    filename = 'Desconhecido'
    url = ''

    if files:
        path = files[0].get('path', '')
        if path:
            filename = os.path.basename(path)
        uris = files[0].get('uris', [])
        if uris:
            url = uris[0].get('uri', '')
            if not path or filename == 'Desconhecido':
                # Extract filename from URL
                url_path = url.split('?')[0].split('#')[0]
                url_name = url_path.rstrip('/').split('/')[-1]
                if url_name:
                    filename = url_name

    total = int(raw.get('totalLength', 0))
    completed = int(raw.get('completedLength', 0))
    speed = int(raw.get('downloadSpeed', 0))

    progress = (completed / total * 100) if total > 0 else 0

    eta = None
    if speed > 0 and total > completed:
        eta_seconds = (total - completed) / speed
        eta = _format_eta(int(eta_seconds))

    return {
        'gid': raw.get('gid'),
        'status': raw.get('status'),
        'filename': filename,
        'url': url,
        'total': total,
        'completed': completed,
        'speed': speed,
        'progress': round(progress, 1),
        'total_human': _format_size(total),
        'completed_human': _format_size(completed),
        'speed_human': _format_size(speed) + '/s' if speed > 0 else '—',
        'eta': eta,
        'error': raw.get('errorMessage', ''),
    }


def _format_size(size_bytes):
    """Format byte count to human-readable string."""
    if size_bytes <= 0:
        return '0 B'
    elif size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 ** 2:
        return f'{size_bytes / 1024:.1f} KB'
    elif size_bytes < 1024 ** 3:
        return f'{size_bytes / 1024 ** 2:.1f} MB'
    else:
        return f'{size_bytes / 1024 ** 3:.2f} GB'


def _format_eta(seconds):
    """Format seconds to human-readable ETA."""
    if seconds < 60:
        return f'{seconds}s'
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f'{m}min {s}s'
    else:
        h, remainder = divmod(seconds, 3600)
        m, _ = divmod(remainder, 60)
        return f'{h}h {m}min'
