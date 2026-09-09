"""Background extraction service for zipped ISOs using 7z."""
import os
import subprocess
import threading
from werkzeug.utils import secure_filename
from app.services.file_processor import process_iso

ARCHIVE_EXTENSIONS = {'.zip', '.7z', '.rar'}

# Global store for active extraction tasks
EXTRACTION_TASKS = {}

def is_archive(filename):
    """Check if the filename has an archive extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ARCHIVE_EXTENSIONS


def _extract_and_process_task(task_id, filepath, dvd_dir, cd_dir, art_dir, app_context, password=None):
    """Background task to extract the archive and process the ISO inside."""
    with app_context():
        EXTRACTION_TASKS[task_id] = {'status': 'extracting', 'message': 'Procurando ISO na pasta...', 'error': None, 'filename': os.path.basename(filepath)}
        print(f"[Extractor] Iniciando extração de {filepath} (Task ID: {task_id})...")
        
        try:
            # 1. List contents and find the largest .iso or .bin file
            # '7z l -ba' outputs the list of files without headers
            cmd_list = ['7z', 'l', '-ba', '-slt']
            if password:
                cmd_list.append(f'-p{password}')
            cmd_list.append(filepath)
            result = subprocess.run(cmd_list, capture_output=True, text=True, check=True)
            
            largest_file = None
            largest_size = -1
            current_file = None
            
            # parse -slt format which is key=value lines separated by blank lines
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('Path = '):
                    current_file = line[7:]
                elif line.startswith('Size = ') and current_file:
                    size = int(line[7:])
                    ext = os.path.splitext(current_file)[1].lower()
                    if ext in ('.iso', '.bin', '.img') and size > largest_size:
                        largest_size = size
                        largest_file = current_file

            if not largest_file:
                msg = f"Nenhuma ISO encontrada dentro de {filepath}"
                EXTRACTION_TASKS[task_id]['status'] = 'error'
                EXTRACTION_TASKS[task_id]['error'] = msg
                print(f"[Extractor] Erro: {msg}")
                os.remove(filepath)
                return

            print(f"[Extractor] ISO encontrada: {largest_file} ({largest_size} bytes)")
            EXTRACTION_TASKS[task_id]['message'] = f'Extraindo {os.path.basename(largest_file)}...'
            
            # 2. Extract specifically that file into the same directory as the archive
            work_dir = os.path.dirname(filepath)
            
            # Extract preserving paths is usually e (extract flat)
            cmd_extract = ['7z', 'e']
            if password:
                cmd_extract.append(f'-p{password}')
            cmd_extract.extend([filepath, f'-o{work_dir}', largest_file, '-y'])
            
            # Subprocess pode falhar se a senha estiver incorreta
            subprocess.run(cmd_extract, capture_output=True, text=True, check=True)
            
            extracted_path = os.path.join(work_dir, os.path.basename(largest_file))
            
            if not os.path.exists(extracted_path):
                EXTRACTION_TASKS[task_id]['status'] = 'error'
                EXTRACTION_TASKS[task_id]['error'] = 'Falha na extração (senha incorreta ou arquivo corrompido)'
                print(f"[Extractor] Erro crítico: O arquivo não foi extraído.")
                os.remove(filepath)
                return

            print(f"[Extractor] Arquivo extraído com sucesso. Processando...")
            EXTRACTION_TASKS[task_id]['status'] = 'processing'
            EXTRACTION_TASKS[task_id]['message'] = 'Processando e movendo...'

            # 3. Process the extracted ISO just like a normal upload
            process_iso(extracted_path, dvd_dir, cd_dir, art_dir)
            
            print(f"[Extractor] Concluído processamento de {largest_file}")
            EXTRACTION_TASKS[task_id]['status'] = 'complete'
            EXTRACTION_TASKS[task_id]['message'] = 'Processamento concluído com sucesso'

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr or e.stdout
            print(f"[Extractor] Erro no comando 7z: {err_msg}")
            EXTRACTION_TASKS[task_id]['status'] = 'error'
            EXTRACTION_TASKS[task_id]['error'] = 'Erro no 7z (Senha incorreta?)'
        except Exception as e:
            print(f"[Extractor] Erro fatal durante a extração: {e}")
            EXTRACTION_TASKS[task_id]['status'] = 'error'
            EXTRACTION_TASKS[task_id]['error'] = str(e)
        finally:
            # 4. Clean up original archive
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass


def start_extraction(task_id, filepath, dvd_dir, cd_dir, art_dir, app, password=None):
    """Start the background thread to extract the archive."""
    EXTRACTION_TASKS[task_id] = {'status': 'waiting', 'message': 'Na fila...', 'error': None, 'filename': os.path.basename(filepath)}
    thread = threading.Thread(
        target=_extract_and_process_task, 
        args=(task_id, filepath, dvd_dir, cd_dir, art_dir, app.app_context, password)
    )
    thread.daemon = True
    thread.start()
    return task_id
