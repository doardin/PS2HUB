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
                            <span class="game-card__badge game-card__type ${typeClass}">${game.type}</span>
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

        // Add button (navigate to uploads tab)
        const addBtn = $('#library-add-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                if(window.PS2Hub && window.PS2Hub.switchTab) {
                    window.PS2Hub.switchTab('uploads');
                }
            });
        }

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

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { loadLibrary };
})();
