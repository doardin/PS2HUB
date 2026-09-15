"""Library API routes — list games from DVD/CD directories."""
import os

from flask import Blueprint, abort, current_app, jsonify, send_file

from app.services.cover_art import download_cover, find_cover
from app.services.file_processor import process_iso
from app.services.game_scanner import get_disk_usage, scan_games

library_bp = Blueprint('library', __name__)


@library_bp.route('/library')
def list_games():
    """Return all games found in DVD/ and CD/ directories.

    Response JSON:
        {
            "games": [...],
            "total": int,
            "disk": { "total": ..., "free": ..., ... }
        }
    """
    dvd_dir = current_app.config['DVD_DIR']
    cd_dir = current_app.config['CD_DIR']
    art_dir = current_app.config['ART_DIR']
    ps2_root = current_app.config['PS2_ROOT']

    games = scan_games(dvd_dir, cd_dir)

    # Check which games have cover art
    for game in games:
        if game['serial']:
            cover = find_cover(art_dir, game['serial'])
            game['has_cover'] = cover is not None
        else:
            game['has_cover'] = False

    disk = get_disk_usage(ps2_root)

    return jsonify({
        'games': games,
        'total': len(games),
        'disk': disk,
    })


@library_bp.route('/art/<serial>')
def get_cover(serial):
    """Serve cover art for a game by serial.

    Tries to find it locally first. If not found, attempts to download
    from the ps2-covers GitHub repository.
    """
    art_dir = current_app.config['ART_DIR']

    # Validate serial format to prevent path traversal
    if not serial or len(serial) > 20 or '..' in serial or '/' in serial:
        abort(400)

    # Try local first
    cover_path = find_cover(art_dir, serial)

    # If not found, try downloading
    if not cover_path:
        cover_path = download_cover(art_dir, serial)

    if not cover_path or not os.path.isfile(cover_path):
        abort(404)

    return send_file(cover_path, mimetype='image/jpeg')


@library_bp.route('/library/<game_type>/<filename>', methods=['DELETE'])
def delete_game(game_type, filename):
    """Delete a game ISO file."""
    from werkzeug.utils import secure_filename
    
    if game_type not in ['DVD', 'CD']:
        return jsonify({'error': 'Tipo de jogo inválido'}), 400

    # Ensure no path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Nome de arquivo inválido'}), 400

    base_dir = current_app.config['DVD_DIR'] if game_type == 'DVD' else current_app.config['CD_DIR']
    file_path = os.path.join(base_dir, filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'Arquivo não encontrado'}), 404

    try:
        os.remove(file_path)
        return jsonify({'message': 'Jogo apagado com sucesso'})
    except Exception as e:
        return jsonify({'error': f'Falha ao apagar o arquivo: {str(e)}'}), 500


@library_bp.route('/library/fix/<game_type>/<filename>', methods=['POST'])
def fix_game(game_type, filename):
    """Reprocess a game ISO to fix its naming and metadata.

    Runs the standard process_iso pipeline on an existing file:
    extracts serial, renames to OPL format, downloads cover art.
    """
    if game_type not in ['DVD', 'CD']:
        return jsonify({'error': 'Tipo de jogo inválido'}), 400

    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Nome de arquivo inválido'}), 400

    dvd_dir = current_app.config['DVD_DIR']
    cd_dir = current_app.config['CD_DIR']
    art_dir = current_app.config['ART_DIR']

    base_dir = dvd_dir if game_type == 'DVD' else cd_dir
    file_path = os.path.join(base_dir, filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'Arquivo não encontrado'}), 404

    try:
        result = process_iso(file_path, dvd_dir, cd_dir, art_dir)
        if result:
            return jsonify({
                'message': 'Jogo corrigido com sucesso',
                'game': result,
            })
        else:
            return jsonify({'error': 'Não foi possível processar o arquivo ISO'}), 422
    except Exception as e:
        return jsonify({'error': f'Erro ao processar: {str(e)}'}), 500

