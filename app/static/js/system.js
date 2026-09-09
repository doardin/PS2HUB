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
            
            updateBadge(els.svcAria2c, data.services.aria2c);
            
        } catch (error) {
            console.error('Error fetching system stats:', error);
            updateBadge(els.svcAria2c, false);
        }
    }

    function init() {
        if (document.getElementById('section-system')) {
            fetchSystemStats();
            setInterval(fetchSystemStats, POLL_INTERVAL);
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
