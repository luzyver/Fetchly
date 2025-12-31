const AdminAPI = {
    async request(endpoint, method = 'GET', data = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) options.body = JSON.stringify(data);
        
        const res = await fetch(endpoint, options);
        return { ok: res.ok, data: res.ok ? await res.json().catch(() => ({})) : null };
    },

    deleteTask(taskId) {
        return this.request(`/admin/delete_task/${taskId}`, 'DELETE');
    },

    addToWhitelist(userId, note) {
        return this.request('/admin/whitelist/add', 'POST', { user_id: userId, note });
    },

    removeFromWhitelist(userId) {
        return this.request(`/admin/whitelist/remove/${userId}`, 'DELETE');
    },

    addToBlacklist(ip, reason) {
        return this.request('/admin/blacklist/add', 'POST', { ip, reason });
    },

    removeFromBlacklist(ip) {
        return this.request(`/admin/blacklist/remove/${ip}`, 'DELETE');
    }
};

window.AdminAPI = AdminAPI;
