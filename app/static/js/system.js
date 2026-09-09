/**
 * PS2 Hub — System module (Phase 4)
 */

const PS2System = (() => {
    'use strict';

    const POLL_INTERVAL = 5000;
    
    // Elements
    const els = {
        cpuText: document.getElementById('sys-cpu-text'),
        cpuBar: document.getElementById('sys-cpu-bar'),
        ramText: document.getElementById('sys-ram-text'),
        ramBar: document.getElementById('sys-ram-bar'),
        ramDetail: document.getElementById('sys-ram-detail'),
        diskText: document.getElementById('sys-disk-text'),
        diskBar: document.getElementById('sys-disk-bar'),
        diskDetail: document.getElementById('sys-disk-detail'),
        svcSmbd: document.getElementById('sys-service-smbd'),
        svcAria2c: document.getElementById('sys-service-aria2c'),
    };

    function formatBytes(bytes) {
        if (bytes === 0) return '0 GB';
        const gb = bytes / (1024 * 1024 * 1024);
        return gb.toFixed(2) + ' GB';
    }

    function updateBadge(element, isRunning) {
        if (!element) return;
        if (isRunning) {
            element.textContent = 'Rodando';
            element.classList.remove('status-badge--danger');
            element.classList.add('status-badge--success');
        } else {
            element.textContent = 'Parado';
            element.classList.remove('status-badge--success');
            element.classList.add('status-badge--danger');
        }
    }

    async function fetchSystemStats() {
        try {
            const response = await fetch('/api/system/stats');
            if (!response.ok) throw new Error('Network response was not ok');
            
            const data = await response.json();
            
            if(els.cpuText) els.cpuText.textContent = `${data.cpu.percent.toFixed(1)}%`;
            if(els.cpuBar) els.cpuBar.style.width = `${data.cpu.percent}%`;
            
            if(els.ramText) els.ramText.textContent = `${data.ram.percent.toFixed(1)}%`;
            if(els.ramBar) els.ramBar.style.width = `${data.ram.percent}%`;
            if(els.ramDetail) els.ramDetail.textContent = `${formatBytes(data.ram.used)} / ${formatBytes(data.ram.total)}`;
            
            if(els.diskText) els.diskText.textContent = `${data.disk.percent.toFixed(1)}%`;
            if(els.diskBar) els.diskBar.style.width = `${data.disk.percent}%`;
            if(els.diskDetail) els.diskDetail.textContent = `${formatBytes(data.disk.used)} / ${formatBytes(data.disk.total)}`;
            
            updateBadge(els.svcSmbd, data.services.smbd);
            updateBadge(els.svcAria2c, data.services.aria2c);
            
        } catch (error) {
            console.error('Error fetching system stats:', error);
            updateBadge(els.svcSmbd, false);
            updateBadge(els.svcAria2c, false);
        }
    }

    // ── Service control ────────────────────────────────────────────
    async function controlService(serviceName, action, btn) {
        // Disable all buttons for this service while working
        const row = btn.closest('.service-item');
        const buttons = row.querySelectorAll('.svc-btn');
        buttons.forEach(b => b.disabled = true);
        btn.classList.add('svc-btn--loading');

        try {
            const resp = await fetch(`/api/system/service/${serviceName}/${action}`, {
                method: 'POST'
            });
            const data = await resp.json();

            if (!data.ok) {
                console.error('Service control error:', data.error);
            }

            // Refresh stats immediately to update badge
            await fetchSystemStats();

        } catch (err) {
            console.error('Service control failed:', err);
        } finally {
            buttons.forEach(b => b.disabled = false);
            btn.classList.remove('svc-btn--loading');
        }
    }

    function bindServiceButtons() {
        document.querySelectorAll('.svc-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const service = btn.dataset.service;
                const action = btn.dataset.action;
                controlService(service, action, btn);
            });
        });
    }

    function init() {
        if (document.getElementById('section-system')) {
            fetchSystemStats();
            setInterval(fetchSystemStats, POLL_INTERVAL);
            bindServiceButtons();
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        init,
        fetchSystemStats,
        controlService
    };
})();
