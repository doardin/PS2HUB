"""Background tasks API routes."""
from flask import Blueprint, jsonify
from app.services.extractor import EXTRACTION_TASKS

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/extractions', methods=['GET'])
def get_extractions():
    """Retorna o status de todas as tarefas de extração ativas ou concluídas."""
    # Filtrar chaves internas (como _on_success, que é uma função e não serializa)
    safe_tasks = {}
    for task_id, task_data in EXTRACTION_TASKS.items():
        safe_tasks[task_id] = {k: v for k, v in task_data.items() if not k.startswith('_')}
        
    return jsonify({
        'tasks': safe_tasks
    })

@tasks_bp.route('/extractions/<task_id>', methods=['DELETE'])
def delete_extraction(task_id):
    """Remove uma tarefa de extração do rastreamento (geralmente após ser concluída ou visualizada)."""
    if task_id in EXTRACTION_TASKS:
        del EXTRACTION_TASKS[task_id]
        return jsonify({'message': 'Task removida'})
    return jsonify({'error': 'Task não encontrada'}), 404

@tasks_bp.route('/extractions/<task_id>/retry', methods=['POST'])
def retry_extraction(task_id):
    """Retenta uma extração que falhou."""
    import os
    from flask import request, current_app
    from app.services.extractor import start_extraction
    
    task = EXTRACTION_TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Task não encontrada'}), 404
        
    password = request.json.get('password') if request.is_json else None

    filepath = task.get('_filepath')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Arquivo original não encontrado'}), 404

    try:
        start_extraction(
            task_id, 
            filepath, 
            task['_dvd_dir'], 
            task['_cd_dir'], 
            task['_art_dir'], 
            current_app._get_current_object(), 
            password=password, 
            on_success=task.get('_on_success')
        )
        return jsonify({'message': 'Extração reiniciada', 'task_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
