"""Background tasks API routes."""
from flask import Blueprint, jsonify
from app.services.extractor import EXTRACTION_TASKS

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/extractions', methods=['GET'])
def get_extractions():
    """Retorna o status de todas as tarefas de extração ativas ou concluídas."""
    return jsonify({
        'tasks': EXTRACTION_TASKS
    })

@tasks_bp.route('/extractions/<task_id>', methods=['DELETE'])
def delete_extraction(task_id):
    """Remove uma tarefa de extração do rastreamento (geralmente após ser concluída ou visualizada)."""
    if task_id in EXTRACTION_TASKS:
        del EXTRACTION_TASKS[task_id]
        return jsonify({'message': 'Task removida'})
    return jsonify({'error': 'Task não encontrada'}), 404
