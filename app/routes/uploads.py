"""Uploads API routes — handles chunked file uploads from the browser."""
import os
import uuid

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from app.services.file_processor import is_valid_iso, process_iso

uploads_bp = Blueprint('uploads', __name__)

# Temporary directory for ongoing uploads
_TEMP_DIR = 'temp_uploads'


def _get_temp_dir():
    """Ensure temp directory exists and return its path."""
    path = os.path.join(current_app.config['DOWNLOADS_DIR'], _TEMP_DIR)
    os.makedirs(path, exist_ok=True)
    return path


@uploads_bp.route('/uploads/init', methods=['POST'])
def init_upload():
    """Initialize a new chunked upload session."""
    data = request.get_json(silent=True) or {}
    filename = data.get('filename')
    total_size = data.get('totalSize')

    if not filename:
        return jsonify({'error': 'Nome do arquivo não fornecido'}), 400

    if not total_size or not isinstance(total_size, (int, float)):
        return jsonify({'error': 'Tamanho total inválido'}), 400

    # Basic extension validation
    ext = os.path.splitext(filename)[1].lower()
    if ext not in current_app.config.get('ALLOWED_EXTENSIONS', {'.iso', '.bin', '.img', '.zip', '.7z', '.rar'}):
        return jsonify({'error': 'Formato de arquivo não permitido'}), 400

    # Generate a unique ID for this upload session
    upload_id = str(uuid.uuid4())
    safe_name = secure_filename(filename)

    # Create an empty temp file to hold the chunks
    temp_path = os.path.join(_get_temp_dir(), f'{upload_id}_{safe_name}')
    try:
        # Create or truncate
        open(temp_path, 'wb').close()
    except OSError as e:
        return jsonify({'error': f'Erro ao criar arquivo temporário: {e}'}), 500

    return jsonify({
        'uploadId': upload_id,
        'filename': safe_name,
        'chunkSize': current_app.config.get('MAX_CHUNK_SIZE', 2 * 1024 * 1024)
    }), 201


@uploads_bp.route('/uploads/<upload_id>/chunk', methods=['POST'])
def upload_chunk(upload_id):
    """Receive a chunk and append it to the temp file."""
    # Validate upload_id
    if not upload_id or not upload_id.replace('-', '').isalnum():
        return jsonify({'error': 'ID de upload inválido'}), 400

    filename = request.form.get('filename')
    chunk_index = request.form.get('chunkIndex', type=int)

    if filename is None or chunk_index is None:
        return jsonify({'error': 'Faltam metadados do chunk'}), 400

    safe_name = secure_filename(filename)
    temp_path = os.path.join(_get_temp_dir(), f'{upload_id}_{safe_name}')

    if not os.path.exists(temp_path):
        return jsonify({'error': 'Sessão de upload não encontrada ou expirada'}), 404

    chunk_file = request.files.get('chunk')
    if not chunk_file:
        return jsonify({'error': 'Nenhum dado recebido'}), 400

    # Append chunk data to the temp file
    try:
        with open(temp_path, 'ab') as f:
            # We assume chunks arrive in order. The client must await each chunk.
            chunk_file.save(f)
            
            # Advise the kernel to drop page cache for this file to prevent 
            # WSL memory exhaustion on very large ISOs.
            if hasattr(os, 'posix_fadvise'):
                try:
                    f.flush()
                    os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
                except Exception:
                    pass
    except OSError as e:
        return jsonify({'error': f'Erro ao salvar chunk: {e}'}), 500

    return jsonify({'message': f'Chunk {chunk_index} recebido'}), 200


@uploads_bp.route('/uploads/<upload_id>/complete', methods=['POST'])
def complete_upload(upload_id):
    """Reassemble the chunks and process the ISO."""
    data = request.json
    filename = data.get('filename')
    password = data.get('password')

    if not filename:
        return jsonify({'error': 'Nome do arquivo não fornecido'}), 400

    safe_name = secure_filename(filename)
    final_path = os.path.join(_get_temp_dir(), f'{upload_id}_{safe_name}')

    if not os.path.exists(final_path):
        return jsonify({'error': 'Arquivo final não encontrado'}), 500

    dvd_dir = current_app.config['DVD_DIR']
    cd_dir = current_app.config['CD_DIR']
    art_dir = current_app.config['ART_DIR']

    try:
        from app.services.extractor import is_archive, start_extraction

        if is_archive(final_path):
            start_extraction(upload_id, final_path, dvd_dir, cd_dir, art_dir, current_app._get_current_object(), password=password)
            return jsonify({
                'message': 'Upload concluído. Extração iniciada em segundo plano.',
                'background': True,
                'task_id': upload_id
            })
        else:
            # Process ISO synchronously (renaming, placing in DVD/CD)
            result = process_iso(final_path, dvd_dir, cd_dir, art_dir)
            if result:
                return jsonify({
                    'message': 'Upload e processamento concluídos com sucesso',
                    'result': result,
                    'background': False
                })
            else:
                return jsonify({'error': 'Falha ao processar a ISO'}), 500
    except Exception as e:
        # Only cleanup on synchronous failure
        if os.path.exists(final_path):
            os.remove(final_path)
        return jsonify({'error': str(e)}), 500


@uploads_bp.route('/uploads/<upload_id>', methods=['DELETE'])
def cancel_upload(upload_id):
    """Cancel an upload and delete the temporary file."""
    if not upload_id or not upload_id.replace('-', '').isalnum():
        return jsonify({'error': 'ID de upload inválido'}), 400

    data = request.get_json(silent=True) or {}
    filename = data.get('filename')
    
    if filename:
        safe_name = secure_filename(filename)
        temp_path = os.path.join(_get_temp_dir(), f'{upload_id}_{safe_name}')
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    return jsonify({'message': 'Upload cancelado'}), 200
