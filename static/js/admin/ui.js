const AdminUI = {
    init() {
        this.initProgressBars();
    },

    initProgressBars() {
        document.querySelectorAll('.progress-bar').forEach(el => {
            el.style.width = el.dataset.width + '%';
        });
    },

    showNotification(message, type = 'info') {
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            info: '#6b7280'
        };

        const notification = document.createElement('div');
        notification.className = 'admin-notification';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: var(--bg-surface);
            border: 1px solid ${colors[type]};
            border-radius: 8px;
            color: white;
            font-size: 14px;
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
};

window.AdminUI = AdminUI;
