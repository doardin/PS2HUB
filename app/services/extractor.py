"""Background extraction service for compressed ISOs using unar/7z."""
import os
import shutil
import subprocess
import threading
from app.services.file_processor import process_iso

ARCHIVE_EXTENSIONS = {'.zip', '.7z', '.rar'}

# Global store for active extraction tasks
EXTRACTION_TASKS = {}
_TASKS_LOCK = threading.Lock()

ISO_EXTENSIONS = {'.iso', '.bin', '.img'}
MIN_ISO_SIZE = 1024 * 1024  # 1 MB — skip junk files


def is_archive(filename):
    """Check if the filename has an archive extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ARCHIVE_EXTENSIONS


def _has_command(cmd):
    """Check if a command is available on the system."""
    try:
        subprocess.run([cmd, '--help'], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _extract_with_unar(filepath, work_dir, password=None):
    """Extract ISO files from a RAR archive using unar.
    
    Returns list of newly extracted file paths.
    """
    # Snapshot before
    before = set()
    for f in os.listdir(work_dir):
        if os.path.isfile(os.path.join(work_dir, f)):
            before.add(f)

    # unar: -D = no containing directory (flat), -f = force overwrite
    cmd = ['unar', '-D', '-f']
    if password:
        cmd.extend(['-p', password])
    cmd.extend(['-o', work_dir, filepath])

    print(f"[Extractor] unar cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[Extractor] unar exit code: {result.returncode}")
    if result.stdout:
        print(f"[Extractor] unar stdout (last 500): {result.stdout[-500:]}")
    if result.stderr:
        print(f"[Extractor] unar stderr: {result.stderr[-500:]}")

    # unar returns 0 on success, but may also return non-zero for warnings
    # We check for extracted files instead of relying solely on return code

    # Find new files
    new_files = []
    for f in os.listdir(work_dir):
        full = os.path.join(work_dir, f)
        if not os.path.isfile(full) or f in before:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in ISO_EXTENSIONS:
            size = os.path.getsize(full)
            if size > MIN_ISO_SIZE:
                new_files.append((full, f, size))
        else:
            # Clean up non-ISO files
            try:
                os.remove(full)
            except OSError:
                pass

    return new_files


def _extract_with_7z(filepath, work_dir, password=None):
    """Extract ISO files from an archive using 7z.
    
    Returns list of newly extracted file paths.
    """
    # Snapshot before
    before = set()
    for f in os.listdir(work_dir):
        if os.path.isfile(os.path.join(work_dir, f)):
            before.add(f)

    # Try targeted extraction with wildcards first
    cmd = ['7z', 'e', '-r', '-aou']
    if password:
        cmd.append(f'-p{password}')
    cmd.extend([filepath, f'-o{work_dir}', '*.iso', '*.bin', '*.img', '-y'])

    print(f"[Extractor] 7z cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[Extractor] 7z exit code: {result.returncode}")

    # Check for "Unsupported Method" error → can't be fixed with 7z
    combined_output = (result.stderr or '') + (result.stdout or '')
    if 'Unsupported Method' in combined_output:
        raise RuntimeError(f"7z: Método de compressão não suportado. Instale o unar: sudo apt install unar")

    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

    # Find new files
    new_files = _scan_new_isos(work_dir, before)

    # If no ISOs found, try full extraction as fallback
    if not new_files:
        print(f"[Extractor] 7z wildcards: nenhuma ISO. Tentando extração completa...")
        cmd_full = ['7z', 'e', '-r', '-aou']
        if password:
            cmd_full.append(f'-p{password}')
        cmd_full.extend([filepath, f'-o{work_dir}', '-y'])

        result = subprocess.run(cmd_full, capture_output=True, text=True, check=True)
        new_files = _scan_new_isos(work_dir, before, cleanup_others=True)

    return new_files


def _scan_new_isos(work_dir, before_set, cleanup_others=False):
    """Scan work_dir for new ISO files not in before_set."""
    new_files = []
    for f in os.listdir(work_dir):
        full = os.path.join(work_dir, f)
        if not os.path.isfile(full) or f in before_set:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in ISO_EXTENSIONS:
            size = os.path.getsize(full)
            if size > MIN_ISO_SIZE:
                new_files.append((full, f, size))
        elif cleanup_others:
            try:
                os.remove(full)
            except OSError:
                pass
    return new_files


def _extract_archive(filepath, work_dir, password=None):
    """Extract ISOs from an archive, choosing the right tool.
    
    Uses unar for .rar files, 7z for .zip/.7z.
    Falls back between tools if the primary one fails.
    
    Returns list of (full_path, filename, size) tuples.
    """
    ext = os.path.splitext(filepath)[1].lower()
    has_unar = _has_command('unar')
    has_7z = _has_command('7z')

    if not has_unar and not has_7z:
        raise RuntimeError("Nenhum descompactador encontrado. Instale: sudo apt install unar p7zip-full")

    errors = []

    if ext == '.rar':
        # Prefer unar for RAR files (full RAR5 support)
        if has_unar:
            try:
                result = _extract_with_unar(filepath, work_dir, password)
                if result:
                    return result
                print("[Extractor] unar: nenhuma ISO encontrada")
            except Exception as e:
                errors.append(f"unar: {e}")
                print(f"[Extractor] unar falhou: {e}")

        # Fallback to 7z
        if has_7z:
            try:
                result = _extract_with_7z(filepath, work_dir, password)
                if result:
                    return result
                print("[Extractor] 7z: nenhuma ISO encontrada")
            except Exception as e:
                errors.append(f"7z: {e}")
                print(f"[Extractor] 7z falhou: {e}")
    else:
        # For .zip/.7z, prefer 7z
        if has_7z:
            try:
                result = _extract_with_7z(filepath, work_dir, password)
                if result:
                    return result
                print("[Extractor] 7z: nenhuma ISO encontrada")
            except Exception as e:
                errors.append(f"7z: {e}")
                print(f"[Extractor] 7z falhou: {e}")

        # Fallback to unar (only works for RAR, but won't hurt to try)
        if has_unar and ext == '.rar':
            try:
                result = _extract_with_unar(filepath, work_dir, password)
                if result:
                    return result
            except Exception as e:
                errors.append(f"unar: {e}")

    if errors:
        raise RuntimeError(f"Falha na extração: {'; '.join(errors)}")
    return []


def _extract_and_process_task(task_id, filepath, dvd_dir, cd_dir, art_dir, app_context, password=None, on_success=None):
    """Background task to extract the archive and process ALL ISOs inside."""
    with app_context():
        if task_id not in EXTRACTION_TASKS:
            EXTRACTION_TASKS[task_id] = {}
        EXTRACTION_TASKS[task_id].update({
            'status': 'extracting', 
            'message': 'Extraindo ISOs do arquivo...', 
            'error': None, 
            'filename': os.path.basename(filepath)
        })
        print(f"[Extractor] Iniciando extração de {filepath} (Task ID: {task_id})...")
        
        try:
            work_dir = os.path.dirname(filepath)
            
            # 1. Extract all ISOs using the appropriate tool
            new_iso_files = _extract_archive(filepath, work_dir, password)
            
            if not new_iso_files:
                msg = f"Nenhuma ISO encontrada dentro de {os.path.basename(filepath)}"
                EXTRACTION_TASKS[task_id]['status'] = 'error'
                EXTRACTION_TASKS[task_id]['error'] = msg
                print(f"[Extractor] Erro: {msg}")
                return

            total_isos = len(new_iso_files)
            print(f"[Extractor] {total_isos} ISO(s) extraída(s): {[name for _, name, _ in new_iso_files]}")
            EXTRACTION_TASKS[task_id]['message'] = f'{total_isos} ISO(s) extraída(s). Processando...'
            
            # 2. Process each extracted ISO
            imported_count = 0
            errors = []
            
            for idx, (iso_full_path, iso_name, iso_size) in enumerate(new_iso_files, 1):
                EXTRACTION_TASKS[task_id]['message'] = f'Processando {iso_name} ({idx}/{total_isos})...'
                EXTRACTION_TASKS[task_id]['status'] = 'processing'
                print(f"[Extractor] Processando ({idx}/{total_isos}): {iso_name}")
                
                try:
                    proc_result = process_iso(iso_full_path, dvd_dir, cd_dir, art_dir)
                    if proc_result and os.path.isfile(proc_result.get('path', '')):
                        imported_count += 1
                        print(f"[Extractor] Importado: {iso_name} → {proc_result['type']}/{proc_result['filename']}")
                    else:
                        errors.append(f'{iso_name}: Falha no processamento')
                        print(f"[Extractor] Falha ao processar {iso_name}")
                        if os.path.exists(iso_full_path):
                            try:
                                os.remove(iso_full_path)
                            except OSError:
                                pass
                except Exception as e:
                    errors.append(f'{iso_name}: {str(e)}')
                    print(f"[Extractor] Erro ao processar {iso_name}: {e}")
                    if os.path.exists(iso_full_path):
                        try:
                            os.remove(iso_full_path)
                        except OSError:
                            pass

            # 3. Final status
            if imported_count == 0:
                EXTRACTION_TASKS[task_id]['status'] = 'error'
                EXTRACTION_TASKS[task_id]['error'] = f"Nenhuma ISO importada. Erros: {'; '.join(errors)}" if errors else "Nenhuma ISO válida encontrada"
                print(f"[Extractor] Nenhuma ISO importada de {filepath}")
                return
            
            if errors:
                msg = f'{imported_count}/{total_isos} ISO(s) importada(s)'
                print(f"[Extractor] {msg}. Erros: {errors}")
            else:
                msg = f'{imported_count} ISO(s) importada(s) com sucesso'
                print(f"[Extractor] {msg}")
            
            EXTRACTION_TASKS[task_id]['status'] = 'complete'
            EXTRACTION_TASKS[task_id]['message'] = msg

            # Only discard the source after at least one game was imported.
            try:
                os.remove(filepath)
            except OSError as e:
                print(f"[Extractor] Jogo(s) importado(s), mas não foi possível remover o compactado: {e}")

            if on_success:
                try:
                    on_success()
                except Exception as e:
                    print(f"[Extractor] Jogo(s) importado(s), mas a limpeza do download falhou: {e}")

        except RuntimeError as e:
            print(f"[Extractor] Erro: {e}")
            EXTRACTION_TASKS[task_id]['status'] = 'error'
            EXTRACTION_TASKS[task_id]['error'] = str(e)
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr or e.stdout or str(e)
            print(f"[Extractor] Erro no comando: {err_msg}")
            EXTRACTION_TASKS[task_id]['status'] = 'error'
            EXTRACTION_TASKS[task_id]['error'] = 'Erro na extração (Senha incorreta?)'
        except Exception as e:
            print(f"[Extractor] Erro fatal durante a extração: {e}")
            EXTRACTION_TASKS[task_id]['status'] = 'error'
            EXTRACTION_TASKS[task_id]['error'] = str(e)


def start_extraction(task_id, filepath, dvd_dir, cd_dir, art_dir, app, password=None, on_success=None):
    """Start extraction once per task; failed tasks may be retried."""
    with _TASKS_LOCK:
        existing = EXTRACTION_TASKS.get(task_id)
        if existing and existing['status'] in ('waiting', 'extracting', 'processing', 'complete'):
            return task_id
        EXTRACTION_TASKS[task_id] = {
            'status': 'waiting', 
            'message': 'Na fila...', 
            'error': None, 
            'filename': os.path.basename(filepath),
            '_filepath': filepath,
            '_dvd_dir': dvd_dir,
            '_cd_dir': cd_dir,
            '_art_dir': art_dir,
            '_on_success': on_success
        }
        try:
            thread = threading.Thread(
                target=_extract_and_process_task,
                args=(task_id, filepath, dvd_dir, cd_dir, art_dir, app.app_context, password, on_success)
            )
            thread.daemon = True
            thread.start()
        except Exception as e:
            EXTRACTION_TASKS[task_id]['status'] = 'error'
            EXTRACTION_TASKS[task_id]['error'] = str(e)
            raise
    return task_id
