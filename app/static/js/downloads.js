/**
 * PS2 Hub — Downloads module
 * Manages downloads via aria2 integration.
 */

const PS2Downloads = (() => {
    'use strict';

    // ── State ──────────────────────────────────────────────────
    let pollInterval = null;
    let isActive = false;
    let processedGids = new Set();

    // ── DOM ────────────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);

    // ── Status labels ──────────────────────────────────────────
    const STATUS_MAP = {
        active:   { label: 'Baixando',  class: 'dl-status--active' },
        waiting:  { label: 'Na fila',   class: 'dl-status--waiting' },
        paused:   { label: 'Pausado',   class: 'dl-status--paused' },
        complete: { label: 'Concluído', class: 'dl-status--complete' },
        error:    { label: 'Erro',      class: 'dl-status--error' },
        removed:  { label: 'Removido',  class: 'dl-status--error' },
    };

    // ── Polling ────────────────────────────────────────────────
    function startPolling() {
        if (pollInterval) return;
        refreshDownloads();
        pollInterval = setInterval(refreshDownloads, 2000);
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    // ── API ────────────────────────────────────────────────────
    async function refreshDownloads() {
        try {
            const data = await PS2Hub.api('/downloads');

            if (!data.available) {
                showAria2Error(data.error);
                return;
            }

            // Fetch background extractions
            let extractionsList = [];
            try {
                const extRes = await fetch('/api/extractions');
                if (extRes.ok) {
                    const extData = await extRes.json();
                    const tasks = extData.tasks || {};
                    for (const [taskId, task] of Object.entries(tasks)) {
                        // Aria2 GIDs are 16 chars hex, UUIDs are 36 chars.
                        if (taskId.length !== 16) continue;

                        let dlStatus = 'waiting';
                        if (task.status === 'extracting' || task.status === 'processing') dlStatus = 'active';
                        else if (task.status === 'complete') dlStatus = 'complete';
                        else if (task.status === 'error') dlStatus = 'error';

                        extractionsList.push({
                            gid: taskId,
                            filename: task.filename || 'Descompactando...',
                            status: dlStatus,
                            progress: (task.status === 'complete') ? 100 : 0,
                            total_human: 'Aguarde',
                            completed_human: '-',
                            speed_human: task.message || '',
                            error: task.error,
                            isExtraction: true
                        });
                    }
                }
            } catch (err) {
                console.error('[Downloads] Error fetching extractions:', err);
            }

            hideAria2Error();
            renderDownloads([...data.downloads, ...extractionsList]);

            // Auto-process completed downloads
            for (const dl of data.downloads) {
                if (dl.status === 'complete' && !processedGids.has(dl.gid)) {
                    processedGids.add(dl.gid);
                    processDownload(dl.gid);
                }
            }
        } catch (err) {
            console.error('[Downloads] Refresh error:', err);
        }
    }

    async function addDownload() {
        const input = $('#download-url-input');
        const pwdInput = $('#download-password-input');
        const hint = $('#download-hint');
        const url = input.value.trim();
        const password = pwdInput ? pwdInput.value.trim() : '';

        if (!url) {
            showHint('Cole uma URL para baixar', 'error');
            return;
        }

        // Basic client-side validation
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            showHint('Apenas URLs HTTP/HTTPS são permitidas', 'error');
            return;
        }

        try {
            const data = await PS2Hub.api('/downloads', {
                method: 'POST',
                body: JSON.stringify({ url, password }),
            });

            input.value = '';
            if (pwdInput) pwdInput.value = '';
            showHint('Download adicionado!', 'success');
            refreshDownloads();
        } catch (err) {
            showHint('Erro ao adicionar download', 'error');
        }
    }

    async function pauseDownload(gid) {
        try {
            await PS2Hub.api(`/downloads/${gid}/pause`, { method: 'POST' });
            refreshDownloads();
        } catch (err) {
            console.error('[Downloads] Pause error:', err);
        }
    }

    async function resumeDownload(gid) {
        try {
            await PS2Hub.api(`/downloads/${gid}/resume`, { method: 'POST' });
            refreshDownloads();
        } catch (err) {
            console.error('[Downloads] Resume error:', err);
        }
    }

    async function cancelDownload(gid) {
        try {
            await PS2Hub.api(`/downloads/${gid}`, { method: 'DELETE' });
            refreshDownloads();
        } catch (err) {
            console.error('[Downloads] Cancel error:', err);
        }
    }

    async function processDownload(gid) {
        try {
            const result = await PS2Hub.api(`/downloads/${gid}/process`, { method: 'POST' });
            if (result.result) {
                showHint(
                    `✓ ${result.result.filename} → ${result.result.type}/`,
                    'success'
                );
                // Refresh library if on that tab
                if (typeof PS2Library !== 'undefined') {
                    PS2Library.loadLibrary();
                }
            }
            refreshDownloads();
        } catch (err) {
            // Not a valid ISO or processing failed — that's ok
            console.warn('[Downloads] Process skipped:', err);
        }
    }

    async function dismissExtraction(gid) {
        try {
            await fetch(`/api/extractions/${gid}`, { method: 'DELETE' });
            refreshDownloads();
        } catch (err) {}
    }

    // ── Render ─────────────────────────────────────────────────
    function renderDownloads(downloads) {
        const list = $('#downloads-list');
        const empty = $('#downloads-empty');

        if (downloads.length === 0) {
            list.innerHTML = '';
            empty.hidden = false;
            return;
        }

        empty.hidden = true;

        // Sort: active first, then waiting, paused, complete, error
        const order = { active: 0, waiting: 1, paused: 2, complete: 3, error: 4, removed: 5 };
        downloads.sort((a, b) => (order[a.status] || 9) - (order[b.status] || 9));

        list.innerHTML = downloads.map(dl => {
            const info = STATUS_MAP[dl.status] || STATUS_MAP.error;
            const isDownloading = dl.status === 'active';
            const isPaused = dl.status === 'paused';
            const isComplete = dl.status === 'complete';
            const isError = dl.status === 'error';

            const progressPercent = Math.min(dl.progress, 100);

            let detailsHtml = '';
            if (isDownloading || isPaused) {
                detailsHtml = `
                    <span>${progressPercent.toFixed(1)}% • ${dl.completed_human} / ${dl.total_human}</span>
                    <span>${dl.speed_human}${dl.eta ? ` • ~${dl.eta}` : ''}</span>
                `;
            } else if (isComplete) {
                detailsHtml = `<span>${dl.total_human}</span><span>Pronto para processar</span>`;
            } else if (isError) {
                detailsHtml = `<span class="dl-error-msg">${dl.error || 'Erro desconhecido'}</span>`;
            }

            let actionsHtml = '';
            if (dl.isExtraction) {
                if (isComplete || isError) {
                    actionsHtml = `<button class="dl-action dl-action--cancel" onclick="PS2Downloads.dismissExtraction('${dl.gid}')">Ocultar</button>`;
                }
            } else {
                if (isDownloading) {
                    actionsHtml = `
                        <button class="dl-action dl-action--pause" onclick="PS2Downloads.pause('${dl.gid}')">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                            Pausar
                        </button>
                        <button class="dl-action dl-action--cancel" onclick="PS2Downloads.cancel('${dl.gid}')">✕</button>
                    `;
                } else if (isPaused) {
                    actionsHtml = `
                        <button class="dl-action dl-action--resume" onclick="PS2Downloads.resume('${dl.gid}')">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                            Continuar
                        </button>
                        <button class="dl-action dl-action--cancel" onclick="PS2Downloads.cancel('${dl.gid}')">✕</button>
                    `;
                } else if (isComplete || isError) {
                    actionsHtml = `
                        <button class="dl-action dl-action--cancel" onclick="PS2Downloads.cancel('${dl.gid}')">Remover</button>
                    `;
                }
            }

            return `
                <div class="dl-item ${isComplete ? 'dl-item--complete' : ''} ${isError ? 'dl-item--error' : ''}">
                    <div class="dl-item__header">
                        <span class="dl-item__name" title="${escapeHtml(dl.filename)}">${escapeHtml(dl.filename)}</span>
                        <span class="dl-status ${info.class}">${info.label}</span>
                    </div>
                    ${(isDownloading || isPaused) ? `
                        <div class="dl-progress">
                            <div class="dl-progress__bar" style="width: ${progressPercent}%"></div>
                        </div>
                    ` : ''}
                    <div class="dl-item__details">${detailsHtml}</div>
                    <div class="dl-item__actions">${actionsHtml}</div>
                </div>
            `;
        }).join('');
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── UI Helpers ─────────────────────────────────────────────
    function showHint(message, type = 'info') {
        const hint = $('#download-hint');
        if (!hint) return;
        hint.textContent = message;
        hint.className = `download-form__hint download-form__hint--${type}`;
        clearTimeout(hint._timer);
        hint._timer = setTimeout(() => {
            hint.textContent = '';
            hint.className = 'download-form__hint';
        }, 5000);
    }

    function showAria2Error(error) {
        const form = $('#download-form');
        const list = $('#downloads-list');
        const empty = $('#downloads-empty');
        const errEl = $('#aria2-error');
        if (form) form.style.display = 'none';
        if (list) list.innerHTML = '';
        if (empty) empty.hidden = true;
        if (errEl) errEl.hidden = false;
    }

    function hideAria2Error() {
        const form = $('#download-form');
        const errEl = $('#aria2-error');
        if (form) form.style.display = '';
        if (errEl) errEl.hidden = true;
    }

    // ── Events ─────────────────────────────────────────────────
    function init() {
        // Add download button
        const addBtn = $('#download-add-btn');
        if (addBtn) {
            addBtn.addEventListener('click', addDownload);
        }

        // Enter key in URL input
        const urlInput = $('#download-url-input');
        if (urlInput) {
            urlInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addDownload();
                }
            });
        }

        // Start/stop polling based on active tab
        document.addEventListener('ps2hub:tabchange', (e) => {
            if (e.detail.tab === 'downloads') {
                startPolling();
            } else {
                stopPolling();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API (needed for inline onclick handlers)
    return {
        pause: pauseDownload,
        resume: resumeDownload,
        cancel: cancelDownload,
        refresh: refreshDownloads,
        dismissExtraction: dismissExtraction,
    };
})();
