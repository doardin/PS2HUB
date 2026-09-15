/**
 * PS2 Hub — Library module
 * Fetches game list from /api/library and renders the grid.
 */

const PS2Library = (() => {
    'use strict';

    // ── State ──────────────────────────────────────────────────
    let allGames = [];
    let currentFilter = 'all';
    let searchQuery = '';
    let currentSort = 'name-asc';

    // ── DOM ────────────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);

    // ── Helper ─────────────────────────────────────────────────
    function getRegionFromSerial(serial) {
        if (!serial) return '';
        const s = serial.toUpperCase();
        if (s.startsWith('SLES') || s.startsWith('SCES')) return 'PAL';
        if (s.startsWith('SLUS') || s.startsWith('SCUS')) return 'NTSC-U';
        if (s.startsWith('SLPM') || s.startsWith('SLPS') || s.startsWith('SCAJ')) return 'NTSC-J';
        return '';
    }

    // ── Color generation from string hash ──────────────────────
    function hashCode(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
            hash |= 0;
        }
        return Math.abs(hash);
    }

    function getGameGradient(str) {
        const hash = hashCode(str);
        const hue1 = hash % 360;
        const hue2 = (hue1 + 35 + (hash % 30)) % 360;
        const sat1 = 35 + (hash % 20);
        const sat2 = 40 + (hash % 25);
        return `linear-gradient(145deg, hsl(${hue1}, ${sat1}%, 15%), hsl(${hue2}, ${sat2}%, 10%))`;
    }

    // ── Render ─────────────────────────────────────────────────
    function renderGames(games) {
        const grid = $('#games-grid');
        const loading = $('#library-loading');
        const empty = $('#library-empty');

        // Hide loading
        if (loading) loading.classList.add('loading--hidden');

        // Clear grid
        grid.innerHTML = '';

        if (games.length === 0) {
            empty.hidden = false;
            if (searchQuery || currentFilter !== 'all') {
                empty.querySelector('.empty-state__title').textContent = 'Nenhum resultado';
                empty.querySelector('.empty-state__desc').textContent = 'Tente outro termo de pesquisa ou filtro';
            } else {
                empty.querySelector('.empty-state__title').textContent = 'Nenhum jogo encontrado';
                empty.querySelector('.empty-state__desc').textContent = 'Adicione ISOs às pastas DVD/ ou CD/ do servidor';
            }
            return;
        }

        empty.hidden = true;

        const fragment = document.createDocumentFragment();

        games.forEach((game, index) => {
            const card = document.createElement('article');
            card.className = 'game-card fade-in';
            card.style.animationDelay = `${Math.min(index * 40, 600)}ms`;
            card.dataset.type = game.type;

            const gradient = getGameGradient(game.id || game.title);
            const serialDisplay = game.serial
                ? game.serial.replace('_', '-')
                : '';
            const typeClass = game.type === 'DVD' ? 'game-card__type--dvd' : 'game-card__type--cd';
            const region = getRegionFromSerial(serialDisplay);

            // Get up to 3 letters for the cover label (fallback when no art)
            const coverLabel = game.title
                .split(/[\s.-]+/)
                .filter(w => w.length > 0)
                .slice(0, 3)
                .map(w => w[0])
                .join('')
                .toUpperCase();

            // Build cover art image if serial is available
            const coverImgHtml = game.serial
                ? `<img class="game-card__cover-img" src="/api/art/${encodeURIComponent(game.serial)}" alt="" loading="lazy" onload="this.classList.add('loaded')" onerror="this.style.display='none'">`
                : '';

            card.innerHTML = `
                <div class="game-card__cover">
                    <div class="game-card__cover-bg" style="background: ${gradient}"></div>
                    <span class="game-card__cover-label">${escapeHtml(coverLabel)}</span>
                    ${coverImgHtml}
                </div>
                <div class="game-card__info">
                    <h3 class="game-card__title" title="${escapeHtml(game.title)}">${escapeHtml(game.title)}</h3>
                    <div class="game-card__meta">
                        <div class="game-card__meta-left">
                            ${serialDisplay ? `<span class="game-card__serial-badge">${escapeHtml(serialDisplay)}</span>` : '<span></span>'}
                        </div>
                        <div class="game-card__actions">
                            <button class="game-card__actions-btn" aria-label="Ações do jogo" aria-expanded="false" aria-controls="menu-${index}">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <circle cx="12" cy="12" r="2"></circle>
                                    <circle cx="12" cy="5" r="2"></circle>
                                    <circle cx="12" cy="19" r="2"></circle>
                                </svg>
                            </button>
                            <div class="game-card__menu" id="menu-${index}" role="menu">
                                <button class="game-card__menu-item game-card__menu-item--danger js-delete-btn" role="menuitem">Excluir</button>
                            </div>
                        </div>
                    </div>
                    <div class="game-card__meta" style="margin-bottom:0;">
                        <span class="game-card__size">${escapeHtml(game.size_human)}</span>
                        ${region ? `<span class="game-card__region">${escapeHtml(region)}</span>` : '<span></span>'}
                    </div>
                </div>
            `;

            // Menu toggle
            const actionBtn = card.querySelector('.game-card__actions-btn');
            const menu = card.querySelector('.game-card__menu');
            
            actionBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isActive = menu.classList.contains('active');
                
                // Close all other menus
                document.querySelectorAll('.game-card__menu.active').forEach(m => {
                    m.classList.remove('active');
                    const b = m.parentElement.querySelector('.game-card__actions-btn');
                    if(b) b.setAttribute('aria-expanded', 'false');
                });

                if (!isActive) {
                    menu.classList.add('active');
                    actionBtn.setAttribute('aria-expanded', 'true');
                }
            });

            // Delete event
            const deleteBtn = card.querySelector('.js-delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                menu.classList.remove('active');
                
                const modal = $('#delete-modal');
                if (!modal) return;
                
                // Set text
                $('#delete-modal-game-name').textContent = game.title;
                
                // Show modal
                modal.hidden = false;
                
                // Setup handlers
                const confirmBtn = $('#delete-modal-confirm');
                const cancelBtn = $('#delete-modal-cancel');
                const closeBtn = $('#delete-modal-close');
                
                const closeModal = () => {
                    modal.hidden = true;
                    // Remove listeners to avoid duplicates
                    confirmBtn.removeEventListener('click', doDelete);
                    cancelBtn.removeEventListener('click', closeModal);
                    closeBtn.removeEventListener('click', closeModal);
                };
                
                const doDelete = async () => {
                    confirmBtn.disabled = true;
                    confirmBtn.textContent = 'Apagando...';
                    
                    try {
                        const res = await fetch(`/api/library/${game.type}/${encodeURIComponent(game.filename)}`, {
                            method: 'DELETE'
                        });
                        
                        if (res.ok) {
                            closeModal();
                            loadLibrary();
                        } else {
                            const err = await res.json().catch(() => ({}));
                            alert(err.error || 'Erro ao apagar o jogo');
                        }
                    } catch (err) {
                        alert('Erro de conexão ao tentar apagar o jogo');
                    } finally {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Apagar Jogo';
                    }
                };
                
                confirmBtn.addEventListener('click', doDelete);
                cancelBtn.addEventListener('click', closeModal);
                closeBtn.addEventListener('click', closeModal);
            });

            fragment.appendChild(card);
        });

        grid.appendChild(fragment);

        // Global click to close menus
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.game-card__actions')) {
                document.querySelectorAll('.game-card__menu.active').forEach(m => {
                    m.classList.remove('active');
                    const b = m.parentElement.querySelector('.game-card__actions-btn');
                    if(b) b.setAttribute('aria-expanded', 'false');
                });
            }
        });
        
        // Escape key to close menus
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.game-card__menu.active').forEach(m => {
                    m.classList.remove('active');
                    const b = m.parentElement.querySelector('.game-card__actions-btn');
                    if(b) b.setAttribute('aria-expanded', 'false');
                });
            }
        });
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Filtering & Sorting ────────────────────────────────────
    function applyFilters() {
        let filtered = allGames;

        // Type filter
        if (currentFilter !== 'all') {
            filtered = filtered.filter(g => g.type === currentFilter);
        }

        // Search
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(g =>
                g.title.toLowerCase().includes(q) ||
                (g.serial && g.serial.toLowerCase().includes(q)) ||
                g.filename.toLowerCase().includes(q)
            );
        }

        // Sorting
        filtered.sort((a, b) => {
            switch (currentSort) {
                case 'name-asc':
                    return a.title.localeCompare(b.title);
                case 'name-desc':
                    return b.title.localeCompare(a.title);
                case 'size-desc':
                    return b.size - a.size;
                case 'size-asc':
                    return a.size - b.size;
                case 'type':
                    return a.type.localeCompare(b.type);
                case 'region':
                    const rA = getRegionFromSerial(a.serial);
                    const rB = getRegionFromSerial(b.serial);
                    return rA.localeCompare(rB);
                default:
                    return 0;
            }
        });

        renderGames(filtered);
    }

    // ── API ────────────────────────────────────────────────────
    async function loadLibrary() {
        const refreshBtn = $('#library-refresh-btn');
        const icon = refreshBtn ? refreshBtn.querySelector('svg.scan-icon') : null;
        const scanText = refreshBtn ? refreshBtn.querySelector('.scan-text') : null;
        
        if (refreshBtn) {
            refreshBtn.disabled = true;
            if (scanText) scanText.textContent = 'Escaneando...';
            if (icon) {
                icon.style.transition = 'transform 0.8s linear';
                icon.style.transform = `rotate(${parseInt(icon.dataset.rot || 0) + 360}deg)`;
                icon.dataset.rot = parseInt(icon.dataset.rot || 0) + 360;
            }
        }

        try {
            const data = await PS2Hub.api('/library');
            allGames = data.games || [];

            // Update header stats
            const diskFree = data.disk ? data.disk.free_human : '—';
            PS2Hub.updateHeaderStats(data.total, diskFree);

            applyFilters();
        } catch (err) {
            const loading = $('#library-loading');
            if (loading) {
                loading.classList.add('loading--hidden');
            }
            const empty = $('#library-empty');
            if (empty) {
                empty.hidden = false;
                empty.querySelector('.empty-state__title').textContent = 'Erro ao carregar';
                empty.querySelector('.empty-state__desc').textContent = 'Não foi possível conectar ao servidor';
            }
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
                if (scanText) scanText.textContent = 'Escanear';
            }
        }
    }

    // ── Events ─────────────────────────────────────────────────
    function init() {
        // Search
        const searchInput = $('#search-input');
        if (searchInput) {
            searchInput.addEventListener('input', PS2Hub.debounce((e) => {
                searchQuery = e.target.value.trim();
                applyFilters();
            }, 200));
        }

        // Filter buttons
        const filterBtns = document.querySelectorAll('.filter-btn');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                currentFilter = btn.dataset.filter;
                
                filterBtns.forEach(b => b.classList.remove('filter-btn--active'));
                btn.classList.add('filter-btn--active');
                
                applyFilters();
            });
        });

        // Sort select
        const sortSelect = $('#sort-select');
        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                currentSort = e.target.value;
                applyFilters();
            });
        }

        // Add button → open modal
        const addBtn = $('#library-add-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                openAddGameModal();
            });
        }

        // Initialize the add-game modal
        initAddGameModal();

        // Refresh button
        const refreshBtn = $('#library-refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                loadLibrary();
            });
        }

        // Load data
        loadLibrary();
    }

    // ── Add Game Modal ────────────────────────────────────────
    let activeModalTab = 'modal-download';

    function openAddGameModal() {
        const modal = $('#add-game-modal');
        if (!modal) return;
        modal.hidden = false;

        // Reset state
        const urlInput = $('#modal-download-url');
        const pwdInput = $('#modal-download-password');
        const uploadPwdInput = $('#modal-upload-password');
        const hint = $('#modal-download-hint');
        if (urlInput) urlInput.value = '';
        if (pwdInput) pwdInput.value = '';
        if (uploadPwdInput) uploadPwdInput.value = '';
        if (hint) { hint.textContent = ''; hint.className = 'modal-hint'; }

        // Reset to download tab
        switchModalTab('modal-download');

        // Focus URL input after animation
        setTimeout(() => {
            if (urlInput) urlInput.focus();
        }, 100);
    }

    function closeAddGameModal() {
        const modal = $('#add-game-modal');
        if (modal) modal.hidden = true;
    }

    function switchModalTab(tabName) {
        activeModalTab = tabName;

        // Update tab buttons
        document.querySelectorAll('.modal-tabs__btn').forEach(btn => {
            btn.classList.toggle('modal-tabs__btn--active', btn.dataset.modalTab === tabName);
        });

        // Update panels
        document.querySelectorAll('.modal-panel').forEach(panel => {
            panel.classList.toggle('modal-panel--active', panel.id === `modal-panel-${tabName}`);
        });

        // Update indicator
        updateModalIndicator();

        // Update footer button
        const submitBtn = $('#add-game-modal-submit');
        if (submitBtn) {
            if (tabName === 'modal-download') {
                submitBtn.style.display = '';
                submitBtn.querySelector('span').textContent = 'Baixar';
            } else {
                // Hide submit on upload tab (upload zone handles it)
                submitBtn.style.display = 'none';
            }
        }
    }

    function updateModalIndicator() {
        const activeBtn = document.querySelector(`.modal-tabs__btn[data-modal-tab="${activeModalTab}"]`);
        const indicator = $('#modal-tabs-indicator');
        if (!activeBtn || !indicator) return;

        const rect = activeBtn.getBoundingClientRect();
        const parentRect = activeBtn.parentElement.getBoundingClientRect();

        indicator.style.left = `${rect.left - parentRect.left}px`;
        indicator.style.width = `${rect.width}px`;
    }

    async function handleModalDownload() {
        const urlInput = $('#modal-download-url');
        const pwdInput = $('#modal-download-password');
        const hint = $('#modal-download-hint');
        const url = urlInput ? urlInput.value.trim() : '';
        const password = pwdInput ? pwdInput.value.trim() : '';

        if (!url) {
            showModalHint('Cole uma URL para baixar', 'error');
            if (urlInput) urlInput.focus();
            return;
        }

        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            showModalHint('Apenas URLs HTTP/HTTPS são permitidas', 'error');
            return;
        }

        const submitBtn = $('#add-game-modal-submit');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.querySelector('span').textContent = 'Adicionando...';
        }

        try {
            await PS2Hub.api('/downloads', {
                method: 'POST',
                body: JSON.stringify({ url, password }),
            });

            showModalHint('Download adicionado com sucesso!', 'success');

            // Close modal after a brief delay so user sees the success message
            setTimeout(() => {
                closeAddGameModal();
                // Switch to downloads tab to show progress
                if (window.PS2Hub && window.PS2Hub.switchTab) {
                    window.PS2Hub.switchTab('downloads');
                }
            }, 800);
        } catch (err) {
            showModalHint('Erro ao adicionar download', 'error');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.querySelector('span').textContent = 'Baixar';
            }
        }
    }

    function handleModalUpload(files) {
        if (!files || files.length === 0) return;

        const ALLOWED_EXTENSIONS = ['.iso', '.bin', '.img', '.zip', '.7z', '.rar'];

        // Copy password to the main upload password field so PS2Uploads picks it up
        const modalPwd = $('#modal-upload-password');
        const mainPwd = $('#upload-password-input');
        if (modalPwd && mainPwd) {
            mainPwd.value = modalPwd.value;
        }

        // Validate extensions
        const validFiles = [];
        for (const file of files) {
            const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
            if (!ALLOWED_EXTENSIONS.includes(ext)) {
                alert(`Formato não suportado: ${file.name}\nApenas ISO, BIN, IMG, ZIP, 7Z ou RAR.`);
                continue;
            }
            validFiles.push(file);
        }

        if (validFiles.length === 0) return;

        // Close modal
        closeAddGameModal();

        // Switch to uploads tab and trigger the upload
        if (window.PS2Hub && window.PS2Hub.switchTab) {
            window.PS2Hub.switchTab('uploads');
        }

        // Use the existing PS2Uploads module to process the files
        // We need to access PS2Uploads' processFiles, but it's internal.
        // Instead, we programmatically set the main upload input files and trigger change.
        const mainUploadInput = $('#upload-input');
        if (mainUploadInput) {
            // Create a DataTransfer to set files on the input
            const dt = new DataTransfer();
            validFiles.forEach(f => dt.items.add(f));
            mainUploadInput.files = dt.files;
            mainUploadInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function showModalHint(message, type = 'info') {
        const hint = $('#modal-download-hint');
        if (!hint) return;
        hint.textContent = message;
        hint.className = `modal-hint modal-hint--${type}`;
        clearTimeout(hint._timer);
        hint._timer = setTimeout(() => {
            hint.textContent = '';
            hint.className = 'modal-hint';
        }, 5000);
    }

    function initAddGameModal() {
        // Tab buttons
        document.querySelectorAll('.modal-tabs__btn').forEach(btn => {
            btn.addEventListener('click', () => {
                switchModalTab(btn.dataset.modalTab);
            });
        });

        // Close buttons
        const closeBtn = $('#add-game-modal-close');
        const cancelBtn = $('#add-game-modal-cancel');
        if (closeBtn) closeBtn.addEventListener('click', closeAddGameModal);
        if (cancelBtn) cancelBtn.addEventListener('click', closeAddGameModal);

        // Backdrop click to close
        const backdrop = $('#add-game-modal');
        if (backdrop) {
            backdrop.addEventListener('click', (e) => {
                if (e.target === backdrop) closeAddGameModal();
            });
        }

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const modal = $('#add-game-modal');
                if (modal && !modal.hidden) {
                    closeAddGameModal();
                }
            }
        });

        // Submit button (download)
        const submitBtn = $('#add-game-modal-submit');
        if (submitBtn) {
            submitBtn.addEventListener('click', handleModalDownload);
        }

        // Enter key in URL input
        const urlInput = $('#modal-download-url');
        if (urlInput) {
            urlInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleModalDownload();
                }
            });
        }

        // Modal upload zone
        const modalDropzone = $('#modal-upload-zone');
        const modalFileInput = $('#modal-upload-input');

        if (modalDropzone && modalFileInput) {
            modalDropzone.addEventListener('click', (e) => {
                if (e.target !== modalFileInput) {
                    modalFileInput.click();
                }
            });

            modalFileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleModalUpload(e.target.files);
                    modalFileInput.value = '';
                }
            });

            modalDropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                modalDropzone.classList.add('upload-zone--active');
            });

            modalDropzone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                modalDropzone.classList.remove('upload-zone--active');
            });

            modalDropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                modalDropzone.classList.remove('upload-zone--active');
                if (e.dataTransfer.files.length > 0) {
                    handleModalUpload(e.dataTransfer.files);
                }
            });
        }

        // Set initial indicator position
        requestAnimationFrame(() => updateModalIndicator());
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { loadLibrary };
})();
