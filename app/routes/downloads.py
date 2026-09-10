"""Downloads API routes — manage downloads via aria2."""
import re
import json
import os
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request

from app.services.aria2_client import Aria2Client, Aria2Error, format_download
from app.services.file_processor import is_valid_iso, process_iso

downloads_bp = Blueprint('downloads', __name__)

_PWD_FILE = 'data/passwords.json'

def _save_password(gid, password):
    os.makedirs('data', exist_ok=True)
    pwds = {}
    if os.path.exists(_PWD_FILE):
        try:
            with open(_PWD_FILE, 'r') as f:
                pwds = json.load(f)
        except Exception:
            pass
    pwds[gid] = password
    with open(_PWD_FILE, 'w') as f:
        json.dump(pwds, f)

def _get_password(gid):
    try:
        with open(_PWD_FILE, 'r') as f:
            return json.load(f).get(gid)
    except (OSError, ValueError):
        return None


def _pop_password(gid):
    if not os.path.exists(_PWD_FILE): return None
    try:
        with open(_PWD_FILE, 'r') as f:
            pwds = json.load(f)
        pwd = pwds.pop(gid, None)
        with open(_PWD_FILE, 'w') as f:
            json.dump(pwds, f)
        return pwd
    except Exception:
        return None

def _remove_password(gid):
    _pop_password(gid)


def _get_aria2():
    """Get a configured Aria2Client instance."""
    return Aria2Client(
        rpc_url=current_app.config['ARIA2_RPC_URL'],
        secret=current_app.config['ARIA2_RPC_SECRET'],
    )


def _validate_url(url):
    """Validate that a URL is safe to download.

    Only allows http:// and https:// schemes.
    Rejects file://, ftp://, and other protocols.
    """
    if not url or not isinstance(url, str):
        return False, 'URL não fornecida'

    url = url.strip()
    if len(url) > 4096:
        return False, 'URL muito longa'

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, 'Apenas URLs HTTP/HTTPS são permitidas'

    if not parsed.netloc:
        return False, 'URL inválida'

    # Block localhost/private IPs to prevent SSRF
    hostname = parsed.hostname or ''
    if hostname in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
        return False, 'Downloads de localhost não são permitidos'

    return True, url


# ── Routes ──────────────────────────────────────────────────────

@downloads_bp.route('/downloads', methods=['GET'])
def list_downloads():
    """List all downloads (active + waiting + stopped)."""
    aria2 = _get_aria2()

    try:
        raw_downloads = aria2.list_all()
        # Extraction tasks are displayed by /extractions. Keep the aria2
        # result for recovery, without showing the same download twice.
        from app.services.extractor import EXTRACTION_TASKS
        downloads = [
            format_download(d) for d in raw_downloads
            if d.get('gid') not in EXTRACTION_TASKS
        ]

        return jsonify({
            'downloads': downloads,
            'available': True,
        })
    except Aria2Error as e:
        return jsonify({
            'downloads': [],
            'available': False,
            'error': str(e),
        })


@downloads_bp.route('/downloads', methods=['POST'])
def add_download():
    """Add a new download by URL."""
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    password = data.get('password', '').strip()

    # Validate URL
    valid, result = _validate_url(url)
    if not valid:
        return jsonify({'error': result}), 400

    aria2 = _get_aria2()
    download_dir = current_app.config['DOWNLOADS_DIR']

    try:
        gid = aria2.add_download(result, download_dir=download_dir)
        if password:
            _save_password(gid, password)
        return jsonify({
            'gid': gid,
            'message': 'Download adicionado',
        }), 201
    except Aria2Error as e:
        return jsonify({'error': str(e)}), 503


@downloads_bp.route('/downloads/<gid>/pause', methods=['POST'])
def pause_download(gid):
    """Pause a download."""
    aria2 = _get_aria2()
    try:
        aria2.pause(gid)
        return jsonify({'message': 'Download pausado'})
    except Aria2Error as e:
        return jsonify({'error': str(e)}), 400


@downloads_bp.route('/downloads/<gid>/resume', methods=['POST'])
def resume_download(gid):
    """Resume a paused download."""
    aria2 = _get_aria2()
    try:
        aria2.unpause(gid)
        return jsonify({'message': 'Download retomado'})
    except Aria2Error as e:
        return jsonify({'error': str(e)}), 400


@downloads_bp.route('/downloads/<gid>', methods=['DELETE'])
def cancel_download(gid):
    """Cancel and remove a download."""
    aria2 = _get_aria2()
    try:
        aria2.remove(gid)
        _remove_password(gid)
        return jsonify({'message': 'Download cancelado'})
    except Aria2Error as e:
        return jsonify({'error': str(e)}), 400


@downloads_bp.route('/downloads/<gid>/process', methods=['POST'])
def process_download(gid):
    """Process a completed download: identify, rename, move to library."""
    aria2 = _get_aria2()

    try:
        status = aria2.get_status(gid)
    except Aria2Error as e:
        return jsonify({'error': str(e)}), 400

    if status.get('status') != 'complete':
        return jsonify({'error': 'Download ainda não foi concluído'}), 400

    # Get the downloaded file path
    files = status.get('files', [])
    if not files:
        return jsonify({'error': 'Nenhum arquivo encontrado'}), 400

    filepath = files[0].get('path', '')
    from app.services.extractor import is_archive, start_extraction
    if not filepath or (not is_valid_iso(filepath) and not is_archive(filepath)):
        return jsonify({'error': 'Arquivo não é uma ISO ou compactado válido'}), 400

    # Process the ISO
    dvd_dir = current_app.config['DVD_DIR']
    cd_dir = current_app.config['CD_DIR']
    art_dir = current_app.config['ART_DIR']

    if is_archive(filepath):
        password = _get_password(gid)

        def cleanup_download():
            aria2.remove(gid)
            _remove_password(gid)

        start_extraction(
            gid, filepath, dvd_dir, cd_dir, art_dir,
            current_app._get_current_object(),
            password=password, on_success=cleanup_download,
        )

        return jsonify({
            'message': 'Download concluído. Extração em segundo plano iniciada.',
            'background': True,
            'task_id': gid
        })
    else:
        result = process_iso(filepath, dvd_dir, cd_dir, art_dir)

        if result:
            # Clean up aria2 result entry
            try:
                aria2.remove(gid)
            except Aria2Error:
                pass

            return jsonify({
                'message': 'ISO processada com sucesso',
                'result': result,
            })
        else:
            return jsonify({'error': 'Não foi possível processar a ISO'}), 500


@downloads_bp.route('/downloads/status', methods=['GET'])
def aria2_status():
    """Check if aria2 is available."""
    aria2 = _get_aria2()
    available = aria2.is_available()
    return jsonify({'available': available})
