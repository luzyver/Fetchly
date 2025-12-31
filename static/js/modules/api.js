const API = {
    async post(endpoint, data = {}) {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return { response: res, data: await res.json() };
    },

    async get(endpoint) {
        const res = await fetch(endpoint);
        return { response: res, data: await res.json() };
    },

    async checkLimit(fingerprint) {
        return this.post('/check-limit', { fingerprint });
    },

    async fetchFormats(url, captchaToken = '') {
        return this.post('/fetch-formats', { url, captcha: captchaToken });
    },

    async startConversion(payload) {
        return this.post('/convert', payload);
    },

    async checkStatus(taskId) {
        return this.get(`/status/${taskId}`);
    },

    async loadHistory(fingerprint) {
        return this.post('/history', { fingerprint });
    }
};

window.API = API;
