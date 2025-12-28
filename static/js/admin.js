let refreshInterval;
const REFRESH_RATE = 5000;

document.addEventListener('DOMContentLoaded', () => {
    const isAutoRefresh = localStorage.getItem('adminAutoRefresh') === 'true';
    updateToggleUI(isAutoRefresh);
    if(isAutoRefresh) startRefresh();
    
    animateTableRows();
});

function animateTableRows() {
    const rows = document.querySelectorAll('tbody tr, .md\:hidden > div');
    rows.forEach((row, index) => {
        row.style.opacity = '0';
        row.style.transform = 'translateY(10px)';
        setTimeout(() => {
            row.style.transition = 'all 0.3s ease';
            row.style.opacity = '1';
            row.style.transform = 'translateY(0)';
        }, index * 50);
    });
}

function toggleAutoRefresh() {
    const currentState = localStorage.getItem('adminAutoRefresh') === 'true';
    const newState = !currentState;
    localStorage.setItem('adminAutoRefresh', newState);
    
    updateToggleUI(newState);
    
    if (newState) {
        startRefresh();
        Toast.info('Auto-refresh enabled');
    } else {
        stopRefresh();
        Toast.info('Auto-refresh disabled');
    }
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
    const confirmed = await showConfirmModal(
        'Delete Task',
        'Are you sure you want to permanently delete this task and its file?'
    );
    
    if (!confirmed) return;
    
    Toast.info('Deleting task...');
    
    try {
        const response = await fetch(`/admin/delete_task/${taskId}`, { method: 'DELETE' });
        if (response.ok) {
            Toast.success('Task deleted successfully');
            const row = document.querySelector(`[data-task-id="${taskId}"]`) ||
                        event.target.closest('tr, .md\:hidden > div');
            if (row) {
                row.style.transition = 'all 0.3s ease';
                row.style.opacity = '0';
                row.style.transform = 'translateX(20px)';
                setTimeout(() => window.location.reload(), 300);
            } else {
                window.location.reload();
            }
        } else {
            Toast.error('Failed to delete task');
        }
    } catch (e) {
        console.error(e);
        Toast.error('Network error occurred');
    }
}

function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in';
        
        overlay.innerHTML = `
            <div class="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-scale-in">
                <h3 class="text-lg font-bold text-white mb-2">${title}</h3>
                <p class="text-slate-400 text-sm mb-6">${message}</p>
                <div class="flex gap-3 justify-end">
                    <button id="cancelBtn" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-all">
                        Cancel
                    </button>
                    <button id="confirmBtn" class="px-4 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-all">
                        Delete
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        const cancelBtn = overlay.querySelector('#cancelBtn');
        const confirmBtn = overlay.querySelector('#confirmBtn');
        
        const close = (result) => {
            overlay.classList.add('animate-fade-out');
            setTimeout(() => {
                overlay.remove();
                resolve(result);
            }, 200);
        };
        
        cancelBtn.onclick = () => close(false);
        confirmBtn.onclick = () => close(true);
        overlay.onclick = (e) => {
            if (e.target === overlay) close(false);
        };
    });
}

function showLoadingSkeleton(container, count = 3) {
    container.innerHTML = Array(count).fill(`
        <div class="p-4 space-y-3 animate-pulse">
            <div class="flex justify-between">
                <div class="skeleton skeleton-text w-3/4"></div>
                <div class="skeleton w-3 h-3 rounded-full"></div>
            </div>
            <div class="skeleton skeleton-text w-1/2"></div>
            <div class="flex justify-between items-center pt-2">
                <div class="skeleton skeleton-text w-1/4"></div>
                <div class="skeleton w-20 h-8 rounded-lg"></div>
            </div>
        </div>
    `).join('');
}