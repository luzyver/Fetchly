const AdminActions = {
    async deleteTask(taskId) {
        if (!confirm('Delete this task?')) return;
        
        const { ok } = await AdminAPI.deleteTask(taskId);
        if (ok) {
            this.removeElement(`[data-task-id="${taskId}"]`);
            AdminUI.showNotification('Task deleted', 'success');
        } else {
            AdminUI.showNotification('Failed to delete task', 'error');
        }
    },

    async addToWhitelist() {
        const userId = document.getElementById('userId')?.value.trim();
        const note = document.getElementById('note')?.value.trim();
        
        if (!userId) {
            AdminUI.showNotification('User ID required', 'error');
            return;
        }

        const { ok } = await AdminAPI.addToWhitelist(userId, note);
        if (ok) {
            location.reload();
        } else {
            AdminUI.showNotification('Failed to add to whitelist', 'error');
        }
    },

    async removeFromWhitelist(userId) {
        if (!confirm('Remove from whitelist?')) return;
        
        const { ok } = await AdminAPI.removeFromWhitelist(userId);
        if (ok) {
            this.removeElement(`[data-user-id="${userId}"]`);
            AdminUI.showNotification('Removed from whitelist', 'success');
        } else {
            AdminUI.showNotification('Failed to remove', 'error');
        }
    },

    async addToBlacklist() {
        const ip = document.getElementById('blacklistIp')?.value.trim();
        const reason = document.getElementById('blacklistReason')?.value.trim();
        
        if (!ip) {
            AdminUI.showNotification('IP address required', 'error');
            return;
        }

        const { ok } = await AdminAPI.addToBlacklist(ip, reason);
        if (ok) {
            location.reload();
        } else {
            AdminUI.showNotification('Failed to block IP', 'error');
        }
    },

    async removeFromBlacklist(ip) {
        if (!confirm('Unblock this IP?')) return;
        
        const { ok } = await AdminAPI.removeFromBlacklist(ip);
        if (ok) {
            this.removeElement(`[data-blacklist-ip="${ip}"]`);
            AdminUI.showNotification('IP unblocked', 'success');
        } else {
            AdminUI.showNotification('Failed to unblock', 'error');
        }
    },

    copyFingerprint(fp) {
        navigator.clipboard.writeText(fp).then(() => {
            AdminUI.showNotification('Copied to clipboard', 'success');
        });
    },

    removeElement(selector) {
        document.querySelector(selector)?.remove();
    }
};

window.deleteTask = (id) => AdminActions.deleteTask(id);
window.addToWhitelist = () => AdminActions.addToWhitelist();
window.removeFromWhitelist = (id) => AdminActions.removeFromWhitelist(id);
window.addToBlacklist = () => AdminActions.addToBlacklist();
window.removeFromBlacklist = (ip) => AdminActions.removeFromBlacklist(ip);
window.copyFingerprint = (fp) => AdminActions.copyFingerprint(fp);
