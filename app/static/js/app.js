/**
 * PS2 Hub — Main application logic
 * Handles tab navigation, utilities, and initialization.
 */

const PS2Hub = (() => {
    'use strict';

    // ── State ──────────────────────────────────────────────────
    let activeTab = 'library';

    // ── DOM References ─────────────────────────────────────────
    const $ = (sel, ctx = document) => ctx.querySelector(sel);
    const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

    // ── Tab Navigation ─────────────────────────────────────────
    function initTabs() {
        const tabs = $$('.nav__tab');
        const indicator = $('#nav-indicator');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                if (tabName === activeTab) return;
                switchTab(tabName);
            });
        });

        // Set initial indicator position
        requestAnimationFrame(() => updateIndicator());
    }

    function switchTab(tabName) {
        activeTab = tabName;

        // Update tab buttons
        $$('.nav__tab').forEach(t => {
            t.classList.toggle('nav__tab--active', t.dataset.tab === tabName);
        });

        // Update sections
        $$('.section').forEach(s => {
            s.classList.toggle('section--active', s.id === `section-${tabName}`);
        });

        // Slide indicator
        updateIndicator();

        // Notify module
        const event = new CustomEvent('ps2hub:tabchange', { detail: { tab: tabName } });
        document.dispatchEvent(event);
    }

    function updateIndicator() {
        const activeBtn = $(`.nav__tab[data-tab="${activeTab}"]`);
        const indicator = $('#nav-indicator');
        if (!activeBtn || !indicator) return;

        const rect = activeBtn.getBoundingClientRect();
        const navRect = activeBtn.parentElement.getBoundingClientRect();

        indicator.style.left = `${rect.left - navRect.left}px`;
        indicator.style.width = `${rect.width}px`;
    }

    // ── Header Stats ───────────────────────────────────────────
    function updateHeaderStats(total, diskFree) {
        const gamesEl = $('#stat-games');
        const diskEl = $('#stat-disk');

        if (gamesEl) {
            gamesEl.querySelector('.header__stat-value').textContent = total;
        }
        if (diskEl && diskFree) {
            diskEl.querySelector('.header__stat-value').textContent = diskFree;
        }
    }

    // ── Utilities ──────────────────────────────────────────────
    function debounce(fn, delay = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    }

    async function api(endpoint, options = {}) {
        try {
            const response = await fetch(`/api${endpoint}`, {
                headers: { 'Content-Type': 'application/json' },
                ...options,
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (err) {
            console.error(`[PS2Hub] API error ${endpoint}:`, err);
            throw err;
        }
    }

    // ── Initialization ─────────────────────────────────────────
    function init() {
        initTabs();

        // Recalculate indicator on resize
        window.addEventListener('resize', debounce(() => updateIndicator(), 150));

        console.log('[PS2Hub] Initialized');
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        api,
        debounce,
        updateHeaderStats,
        switchTab,
    };
})();
