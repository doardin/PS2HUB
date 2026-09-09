/**
 * PS2 Hub — Uploads module
 * Handles chunked file uploads via fetch API for large ISOs.
 */

const PS2Uploads = (() => {
    'use strict';

    // ── DOM Elements ───────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const dropzone = $('#upload-zone');
    const fileInput = $('#upload-input');
    const uploadsList = $('#uploads-list');

    // ── State ──────────────────────────────────────────────────
    const activeUploads = new Map(); // id -> { id, file, status, progress, controller, el, serverUploadId, taskId, isBackground, isComplete, isError }
    let tasksPollInterval = null;

    // ── Constants ──────────────────────────────────────────────
    const ALLOWED_EXTENSIONS = ['.iso', '.bin', '.img', '.zip', '.7z', '.rar'];
    const DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024; // 10 MB

    // ── Formatters ─────────────────────────────────────────────
    function formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── UI Helpers ─────────────────────────────────────────────
    function getExtension(filename) {
        return filename.substring(filename.lastIndexOf('.')).toLowerCase();
    }

    function createUploadUI(uploadInfo) {
        const div = document.createElement('div');
        div.className = 'dl-item dl-item--active';
        div.id = `upload-${uploadInfo.id}`;

        div.innerHTML = `
            <div class="dl-item__header">
                <span class="dl-item__name" title="${escapeHtml(uploadInfo.file.name)}">
                    ${escapeHtml(uploadInfo.file.name)}
                </span>
                <span class="dl-status dl-status--active" id="upload-status-${uploadInfo.id}">Preparando</span>
            </div>
            <div class="dl-progress">
                <div class="dl-progress__bar" id="upload-bar-${uploadInfo.id}" style="width: 0%"></div>
            </div>
            <div class="dl-item__details">
                <span id="upload-progress-text-${uploadInfo.id}">0% • 0 B / ${formatSize(uploadInfo.file.size)}</span>
                <span id="upload-speed-${uploadInfo.id}">Calculando...</span>
            </div>
            <div class="dl-item__actions">
                <button class="dl-action dl-action--cancel" onclick="PS2Uploads.cancel('${uploadInfo.id}')">
                    ✕ Cancelar
                </button>
            </div>
        `;

        uploadsList.insertBefore(div, uploadsList.firstChild);
        return div;
    }

    function updateUploadUI(id, progressPercent, uploadedBytes, speedBytes, statusLabel, isComplete = false, isError = false, isWarning = false) {
        const upload = activeUploads.get(id);
        if (!upload || !upload.el) return;

        const bar = upload.el.querySelector(`#upload-bar-${id}`);
        const statusEl = upload.el.querySelector(`#upload-status-${id}`);
        const progressText = upload.el.querySelector(`#upload-progress-text-${id}`);
        const speedText = upload.el.querySelector(`#upload-speed-${id}`);
        const actionsEl = upload.el.querySelector('.dl-item__actions');

        if (bar) bar.style.width = `${progressPercent}%`;
        
        if (statusEl) {
            statusEl.textContent = statusLabel;
            
            let statusClass = 'dl-status--active';
            if (isComplete) statusClass = 'dl-status--complete';
            if (isError) statusClass = 'dl-status--error';
            if (isWarning) statusClass = 'dl-status--waiting';
            
            statusEl.className = `dl-status ${statusClass}`;
        }

        if (progressText) {
            progressText.textContent = `${progressPercent.toFixed(1)}% • ${formatSize(uploadedBytes)} / ${formatSize(upload.file.size)}`;
        }

        if (speedText) {
            speedText.textContent = isComplete ? 'Concluído' : isError ? 'Falha' : isWarning ? 'Aguarde...' : `${formatSize(speedBytes)}/s`;
        }

        if (isComplete || isError || isWarning) {
            upload.el.classList.remove('dl-item--active');
            
            if (isComplete) upload.el.classList.add('dl-item--complete');
            else if (isError) upload.el.classList.add('dl-item--error');
            else if (isWarning) upload.el.style.borderColor = 'rgba(255, 171, 0, 0.4)';
            
            // Allow dismissing
            if (actionsEl) {
                actionsEl.innerHTML = `
                    <button class="dl-action dl-action--cancel" onclick="PS2Uploads.dismiss('${id}')">
                        Ocultar
                    </button>
                `;
            }
        }
    }

    async function pollTasks() {
        let hasActiveTasks = false;
        for (const [id, upload] of activeUploads.entries()) {
            if (upload.isBackground && !upload.isComplete && !upload.isError) {
                hasActiveTasks = true;
                break;
            }
        }

        if (!hasActiveTasks) {
            if (tasksPollInterval) {
                clearInterval(tasksPollInterval);
                tasksPollInterval = null;
            }
            return;
        }

        try {
            const res = await fetch('/api/extractions');
            if (!res.ok) return;
            const data = await res.json();
            const tasks = data.tasks || {};

            for (const [id, upload] of activeUploads.entries()) {
                if (upload.isBackground && !upload.isComplete && !upload.isError && upload.taskId) {
                    const task = tasks[upload.taskId];
                    if (task) {
                        const speedEl = upload.el.querySelector(`#upload-speed-${upload.id}`);
                        if (speedEl) speedEl.textContent = task.message || '';

                        if (task.status === 'complete') {
                            upload.isComplete = true;
                            updateUploadUI(id, 100, upload.file.size, 0, 'Concluído', true);
                            if (typeof PS2Library !== 'undefined') PS2Library.loadLibrary();
                        } else if (task.status === 'error') {
                            upload.isError = true;
                            updateUploadUI(id, upload.progress, 0, 0, 'Erro', false, true);
                            if (speedEl) speedEl.textContent = task.error || 'Falha na extração';
                        }
                    }
                }
            }
        } catch (err) {
            console.error('[Uploads] Error polling tasks:', err);
        }
    }

    // ── Upload Logic ───────────────────────────────────────────
    async function processFiles(files) {
        for (const file of files) {
            const ext = getExtension(file.name);
            if (!ALLOWED_EXTENSIONS.includes(ext)) {
                alert(`Formato não suportado: ${file.name}\nApenas ISO, BIN, IMG, ZIP, 7Z ou RAR.`);
                continue;
            }

            // Generate a local ID for UI tracking before the server assigns one
            const localId = 'local_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
            
            const uploadInfo = {
                id: localId,
                file: file,
                status: 'init',
                progress: 0,
                controller: new AbortController(),
                el: null,
                serverUploadId: null,
                taskId: null,
                isBackground: false,
                isComplete: false,
                isError: false
            };

            uploadInfo.el = createUploadUI(uploadInfo);
            activeUploads.set(localId, uploadInfo);

            startChunkedUpload(uploadInfo).catch(err => {
                if (err.name !== 'AbortError') {
                    console.error('[Upload] Falha:', err);
                    updateUploadUI(localId, uploadInfo.progress, 0, 0, 'Erro', false, true);
                    const speedEl = uploadInfo.el.querySelector(`#upload-speed-${localId}`);
                    if (speedEl) speedEl.textContent = err.message || 'Erro desconhecido';
                }
            });
        }
    }

    async function startChunkedUpload(upload) {
        const file = upload.file;
        const controller = upload.controller;

        // 1. Initialize
        updateUploadUI(upload.id, 0, 0, 0, 'Iniciando...');
        
        let initData;
        try {
            initData = await PS2Hub.api('/uploads/init', {
                method: 'POST',
                body: JSON.stringify({
                    filename: file.name,
                    totalSize: file.size
                }),
                signal: controller.signal
            });
        } catch (err) {
            throw new Error(`Erro na inicialização: ${err.message}`);
        }

        upload.serverUploadId = initData.uploadId;
        const chunkSize = initData.chunkSize || DEFAULT_CHUNK_SIZE;
        const totalChunks = Math.ceil(file.size / chunkSize);
        
        let uploadedBytes = 0;
        let speedEma = 0; // Exponential Moving Average for speed
        const alpha = 0.3; // Smoothing factor

        // 2. Upload chunks sequentially
        for (let i = 0; i < totalChunks; i++) {
            if (controller.signal.aborted) throw new DOMException('Cancelado', 'AbortError');

            const start = i * chunkSize;
            const end = Math.min(start + chunkSize, file.size);
            const chunk = file.slice(start, end);

            const formData = new FormData();
            formData.append('filename', file.name);
            formData.append('chunkIndex', i);
            formData.append('chunk', chunk);

            updateUploadUI(upload.id, (uploadedBytes / file.size) * 100, uploadedBytes, speedEma, `Enviando (${i + 1}/${totalChunks})`);

            const startTime = performance.now();

            try {
                // Not using PS2Hub.api here because we need FormData (no JSON stringify)
                const res = await fetch(`/api/uploads/${upload.serverUploadId}/chunk`, {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });

                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.error || `HTTP ${res.status}`);
                }
            } catch (err) {
                if (err.name === 'AbortError') throw err;
                throw new Error(`Falha no chunk ${i}: ${err.message}`);
            }

            uploadedBytes += chunk.size;
            
            // Calculate speed
            const now = performance.now();
            const elapsedMs = now - startTime;
            // Prevent division by zero if it's too fast (< 1ms)
            const safeMs = Math.max(elapsedMs, 1);
            const currentSpeed = (chunk.size / safeMs) * 1000;
            
            if (speedEma === 0) {
                speedEma = currentSpeed;
            } else {
                speedEma = (alpha * currentSpeed) + ((1 - alpha) * speedEma);
            }

            updateUploadUI(upload.id, (uploadedBytes / file.size) * 100, uploadedBytes, speedEma, `Enviando (${i + 1}/${totalChunks})`);
        }

        // 3. Complete and Process
        updateUploadUI(upload.id, 100, file.size, 0, 'Processando...');

        const passwordInput = document.querySelector('#upload-password-input');
        const password = passwordInput ? passwordInput.value.trim() : '';

        try {
            const completeData = await PS2Hub.api(`/uploads/${upload.serverUploadId}/complete`, {
                method: 'POST',
                body: JSON.stringify({ filename: file.name, password: password }),
                signal: controller.signal
            });

            if (completeData.background) {
                upload.taskId = completeData.task_id;
                upload.isBackground = true;
                updateUploadUI(upload.id, 100, file.size, 0, 'Extraindo...', false, false, true);
                const speedEl = upload.el.querySelector(`#upload-speed-${upload.id}`);
                if (speedEl) speedEl.textContent = 'Na fila...';
                
                if (!tasksPollInterval) {
                    tasksPollInterval = setInterval(pollTasks, 2000);
                }
            } else {
                updateUploadUI(upload.id, 100, file.size, 0, 'Concluído', true);
            }
            
            // Refresh library
            if (typeof PS2Library !== 'undefined') {
                PS2Library.loadLibrary();
            }
        } catch (err) {
            if (err.name === 'AbortError') throw err;
            throw new Error(`Erro no processamento: ${err.message}`);
        }
    }

    // ── Public Actions ─────────────────────────────────────────
    async function cancelUpload(id) {
        const upload = activeUploads.get(id);
        if (!upload) return;

        // Abort fetch requests
        upload.controller.abort();

        // Notify server to clean up if we have a server ID
        if (upload.serverUploadId) {
            try {
                await fetch(`/api/uploads/${upload.serverUploadId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: upload.file.name })
                });
            } catch (err) {
                console.warn('[Upload] Erro ao limpar no servidor:', err);
            }
        }

        updateUploadUI(id, upload.progress, 0, 0, 'Cancelado', false, true);
        const speedEl = upload.el.querySelector(`#upload-speed-${id}`);
        if (speedEl) speedEl.textContent = 'Upload cancelado pelo usuário';
    }

    function dismissUpload(id) {
        const upload = activeUploads.get(id);
        if (upload && upload.el) {
            if (upload.taskId) {
                fetch(`/api/extractions/${upload.taskId}`, { method: 'DELETE' }).catch(() => {});
            }
            upload.el.remove();
            activeUploads.delete(id);
        }
    }

    // ── Events ─────────────────────────────────────────────────
    function init() {
        if (!dropzone || !fileInput) return;

        // Click to open file dialog
        dropzone.addEventListener('click', (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                processFiles(e.target.files);
                fileInput.value = ''; // reset
            }
        });

        // Drag & Drop
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('upload-zone--active');
        });

        dropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropzone.classList.remove('upload-zone--active');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('upload-zone--active');
            
            if (e.dataTransfer.files.length > 0) {
                processFiles(e.dataTransfer.files);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        cancel: cancelUpload,
        dismiss: dismissUpload
    };
})();
