let refreshInterval;
const REFRESH_RATE = 5000;

document.addEventListener('DOMContentLoaded', () => {
    const isAutoRefresh = localStorage.getItem('adminAutoRefresh') === 'true';
    updateToggleUI(isAutoRefresh);
    if(isAutoRefresh) startRefresh();
});

function toggleAutoRefresh() {
    const currentState = localStorage.getItem('adminAutoRefresh') === 'true';
    const newState = !currentState;
    localStorage.setItem('adminAutoRefresh', newState);
    
    updateToggleUI(newState);
    
    if (newState) startRefresh();
    else stopRefresh();
}

function updateToggleUI(isEnabled) {
    const btn = document.getElementById('autoRefreshToggle');
    if (!btn) return;
    const span = btn.querySelector('span');
    
    if (isEnabled) {
        btn.classList.replace('bg-slate-600', 'bg-brand-500');
        span.classList.replace('translate-x-0', 'translate-x-5');
    } else {
        btn.classList.replace('bg-brand-500', 'bg-slate-600');
        span.classList.replace('translate-x-5', 'translate-x-0');
    }
}

function startRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(() => window.location.reload(), REFRESH_RATE);
}

function stopRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
}

async function deleteTask(taskId) {
    if (!confirm('Permanently delete this task and file?')) return;
    try {
        const response = await fetch(`/admin/delete_task/${taskId}`, { method: 'DELETE' });
        if (response.ok) window.location.reload();
        else alert('Failed to delete task');
    } catch (e) { 
        console.error(e);
        alert('Network error');
    }
}
