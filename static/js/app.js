const App = {
    state: {
        currentTaskId: null,
        pollInterval: null,
        isProcessing: false,
        progress: 0,
        formats: [],
        selectedFormat: 'best',
        resolvedUrl: null,
        cookies: null,
        referer: null,
        videoTitle: null,
        fingerprint: null,
        captchaEnabled: false,
        recaptchaSiteKey: '',
        captchaWidgetId: null,
        captchaResponse: '',
        captchaRendered: false
    },

    elements: {},

    async init() {
        this.elements = {
            input: document.getElementById('url'),
            pasteBtn: document.getElementById('pasteBtn'),
            clearBtn: document.getElementById('clearBtn'),
            fetchBtn: document.getElementById('fetchBtn'),
            convertBtn: document.getElementById('convertBtn'),
            btnContent: document.getElementById('btnContent'),
            btnLoader: document.getElementById('btnLoader'),
            fetchContent: document.getElementById('fetchContent'),
            fetchLoader: document.getElementById('fetchLoader'),
            formatSection: document.getElementById('formatSection'),
            formatList: document.getElementById('formatList'),
            usageInfo: document.getElementById('usageInfo'),
            historySection: document.getElementById('historySection'),
            historyList: document.getElementById('historyList'),
            historyEmpty: document.getElementById('historyEmpty'),
            captchaSection: document.getElementById('captchaSection'),
            captchaContainer: document.getElementById('captchaContainer')
        };

        this.initTheme();
        if (!this.elements.input) return;

        await this.initFingerprint();
        this.bindEvents();
        this.checkInputState();
        this.checkUsageLimit();
        this.loadHistory();
    },

    initTheme() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);
        this.updateMetaColor(savedTheme);
        document.getElementById('themeToggle')?.addEventListener('click', () => this.toggleTheme());
    },

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateThemeIcon(newTheme);
        this.updateMetaColor(newTheme);
    },

    updateThemeIcon(theme) {
        const moon = document.getElementById('iconMoon');
        const sun = document.getElementById('iconSun');
        if (theme === 'light') {
            moon?.classList.add('hidden');
            sun?.classList.remove('hidden');
        } else {
            moon?.classList.remove('hidden');
            sun?.classList.add('hidden');
        }
    },

    updateMetaColor(theme) {
        const metaColor = theme === 'light' ? '#ffffff' : '#141517';
        document.querySelector('meta[name="theme-color"]')?.setAttribute('content', metaColor);
    },

    async initFingerprint() {
        this.state.fingerprint = this.generateFingerprint();
    },

    generateFingerprint() {
        const canvas = document.createElement('canvas');
        canvas.width = 200;
        canvas.height = 50;
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f60';
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = '#069';
        ctx.fillText('Fetchly', 2, 15);
        ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
        ctx.fillText('Fetchly', 4, 17);

        const canvasData = canvas.toDataURL();
        const data = [
            canvasData, navigator.userAgent, navigator.language,
            screen.width + 'x' + screen.height, screen.colorDepth,
            new Date().getTimezoneOffset(),
            navigator.hardwareConcurrency || 0,
            navigator.deviceMemory || 0
        ].join('|');

        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            const char = data.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return 'fp_' + Math.abs(hash).toString(16);
    },

    async checkUsageLimit() {
        if (!this.state.fingerprint) return;
        try {
            const res = await fetch('/check-limit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fingerprint: this.state.fingerprint })
            });
            const data = await res.json();
            this.updateUsageDisplay(data);
            
            if (data.captcha_enabled && data.recaptcha_site_key) {
                this.state.captchaEnabled = true;
                this.state.recaptchaSiteKey = data.recaptcha_site_key;
            }
        } catch (e) {
            console.error('Failed to check limit:', e);
        }
    },

    showCaptchaSection() {
        if (!this.elements.captchaSection) return;
        this.elements.captchaSection.classList.remove('hidden');
        
        if (!this.state.captchaRendered) {
            this.renderCaptcha();
        }
    },

    hideCaptchaSection() {
        if (!this.elements.captchaSection) return;
        this.elements.captchaSection.classList.add('hidden');
    },

    renderCaptcha() {
        const container = this.elements.captchaContainer;
        if (!container || this.state.captchaRendered) return;

        const checkRecaptcha = () => {
            if (typeof grecaptcha !== 'undefined' && grecaptcha.render) {
                this.state.captchaWidgetId = grecaptcha.render(container, {
                    sitekey: this.state.recaptchaSiteKey,
                    theme: document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark',
                    callback: (response) => { this.state.captchaResponse = response; },
                    'expired-callback': () => { this.state.captchaResponse = ''; }
                });
                this.state.captchaRendered = true;
            } else {
                setTimeout(checkRecaptcha, 100);
            }
        };
        checkRecaptcha();
    },

    resetCaptcha() {
        if (this.state.captchaWidgetId !== null && typeof grecaptcha !== 'undefined') {
            grecaptcha.reset(this.state.captchaWidgetId);
            this.state.captchaResponse = '';
        }
    },

    updateUsageDisplay(data) {
        const usedMB = Math.round(data.used / (1024 * 1024));
        const limitMB = Math.round(data.limit / (1024 * 1024));
        const remainingMB = Math.round(data.remaining / (1024 * 1024));
        const percent = Math.round((data.used / data.limit) * 100);

        if (this.elements.usageInfo) {
            this.elements.usageInfo.innerHTML = `
                <div class="text-xs text-[var(--text-muted)]">
                    Daily usage: ${usedMB}MB / ${limitMB}MB (${remainingMB}MB remaining)
                </div>
                <div class="h-1 bg-[var(--border-subtle)] rounded-full overflow-hidden mt-1">
                    <div class="h-full ${percent > 80 ? 'bg-red-500' : 'bg-emerald-500'} rounded-full" style="width: ${percent}%"></div>
                </div>
            `;
        }
    },

    async loadHistory() {
        if (!this.state.fingerprint) return;
        try {
            const res = await fetch('/history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fingerprint: this.state.fingerprint })
            });
            const data = await res.json();
            this.renderHistory(data.history || []);
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    },

    renderHistory(history) {
        if (!this.elements.historySection) return;

        if (history.length === 0) {
            this.elements.historyEmpty?.classList.remove('hidden');
            this.elements.historyList.innerHTML = '';
            return;
        }

        this.elements.historyEmpty?.classList.add('hidden');
        this.elements.historyList?.classList.remove('hidden');

        const formatSize = (bytes) => {
            if (!bytes) return '-';
            if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
            if (bytes > 1024) return `${(bytes / 1024).toFixed(1)}KB`;
            return `${bytes}B`;
        };

        this.elements.historyList.innerHTML = history.map(item => `
            <div class="history-item">
                <div class="flex justify-between items-start">
                    <div class="history-title" title="${item.title || 'Unknown'}">${item.title || 'Untitled Video'}</div>
                    ${item.status === 'completed' ? 
                        `<a href="/download/${item.id}?fingerprint=${this.state.fingerprint}" class="text-xs text-[var(--text-main)] hover:underline">Download</a>` : 
                        `<span class="text-xs text-[var(--text-faint)]">${item.status}</span>`}
                </div>
                <div class="history-meta mt-1">
                    <span class="status-dot ${item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'processing'}"></span>
                    <span>${formatSize(item.filesize)}</span>
                    <span class="ml-auto font-mono text-[10px] text-[var(--text-faint)]">${item.id.substring(0,6)}</span>
                </div>
            </div>
        `).join('');
    },

    bindEvents() {
        this.elements.input.addEventListener('input', () => {
            this.checkInputState();
            this.resetFormatSelection();
        });

        this.elements.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.state.isProcessing) {
                this.state.formats.length > 0 ? this.startConversion() : this.fetchFormats();
            }
        });

        this.elements.pasteBtn?.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                this.elements.input.value = text;
                this.checkInputState();
                this.resetFormatSelection();
                Toast.success('URL pasted');
            } catch { Toast.error('Clipboard access denied'); }
        });

        this.elements.clearBtn?.addEventListener('click', () => {
            this.elements.input.value = '';
            this.checkInputState();
            this.resetFormatSelection();
            this.elements.input.focus();
        });

        this.elements.fetchBtn?.addEventListener('click', () => this.fetchFormats());
        this.elements.convertBtn?.addEventListener('click', () => this.startConversion());
    },

    checkInputState() {
        const hasValue = this.elements.input.value.trim().length > 0;
        this.elements.clearBtn?.classList.toggle('hidden', !hasValue);
        this.elements.pasteBtn?.classList.toggle('hidden', hasValue);
    },

    resetFormatSelection() {
        Object.assign(this.state, {
            formats: [], selectedFormat: 'best', resolvedUrl: null,
            cookies: null, referer: null, videoTitle: null
        });
        this.elements.formatSection?.classList.add('hidden');
        this.elements.convertBtn?.classList.add('hidden');
        this.elements.fetchBtn?.classList.remove('hidden');
        this.hideCaptchaSection();
    },

    setFetchLoading(loading) {
        if (!this.elements.fetchBtn) return;
        this.elements.fetchBtn.disabled = loading;
        this.elements.input && (this.elements.input.disabled = loading);
        this.elements.fetchContent?.classList.toggle('hidden', loading);
        this.elements.fetchLoader?.classList.toggle('hidden', !loading);
    },

    setConvertLoading(loading) {
        this.state.isProcessing = loading;
        if (!this.elements.convertBtn) return;
        this.elements.convertBtn.disabled = loading;
        this.elements.input && (this.elements.input.disabled = loading);
        this.elements.btnContent?.classList.toggle('hidden', loading);
        this.elements.btnLoader?.classList.toggle('hidden', !loading);
    },

    fetchFormats() {
        const url = this.elements.input?.value.trim();
        if (!url) { Toast.warning('Enter a URL first'); this.elements.input?.focus(); return; }
        if (!url.startsWith('http')) { Toast.warning('Enter a valid URL'); return; }

        if (this.state.captchaEnabled) {
            this.showCaptchaSection();
            if (!this.state.captchaResponse) {
                Toast.info('Please complete the captcha first');
                return;
            }
        }

        this.doFetchFormats();
    },

    async doFetchFormats() {
        const url = this.elements.input?.value.trim();
        this.setFetchLoading(true);
        Toast.info('Fetching formats...');

        try {
            const res = await fetch('/fetch-formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, captcha: this.state.captchaResponse })
            });
            const data = await res.json();
            
            if (data.captcha_required) {
                this.resetCaptcha();
                this.showCaptchaSection();
                throw new Error(data.error || 'Captcha required');
            }
            
            if (!res.ok) throw new Error(data.error || 'Failed to fetch');

            Object.assign(this.state, {
                formats: data.formats || [],
                resolvedUrl: data.resolved_url,
                cookies: data.cookies,
                referer: data.referer,
                videoTitle: data.title
            });

            this.renderFormatSelection();
            this.hideCaptchaSection();
            Toast.success(`Found ${this.state.formats.length} formats`);
            this.resetCaptcha();
        } catch (e) {
            Toast.error(e.message);
        } finally {
            this.setFetchLoading(false);
        }
    },

    renderFormatSelection() {
        if (!this.elements.formatSection || !this.elements.formatList) return;

        this.elements.formatSection.classList.remove('hidden');
        this.elements.fetchBtn?.classList.add('hidden');
        this.elements.convertBtn?.classList.remove('hidden');

        const videoTitle = document.getElementById('videoTitle');
        if (videoTitle && this.state.videoTitle) {
            videoTitle.textContent = this.state.videoTitle;
            videoTitle.title = this.state.videoTitle;
        }

        this.elements.formatList.innerHTML = this.state.formats.map((fmt, i) => `
            <label class="format-option ${i === 0 ? 'selected' : ''}">
                <input type="radio" name="format" value="${fmt.format_id}" ${i === 0 ? 'checked' : ''} class="hidden">
                <div class="flex justify-between items-center w-full">
                    <span class="font-medium text-[var(--text-main)]">${fmt.resolution || 'Auto'}</span>
                </div>
                <div class="format-meta">
                    ${fmt.ext.toUpperCase()} ${fmt.filesize ? '• ' + fmt.filesize : ''}
                </div>
            </label>`).join('');

        this.elements.formatList.querySelectorAll('input[name="format"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.state.selectedFormat = e.target.value;
                this.elements.formatList.querySelectorAll('.format-option').forEach(opt => opt.classList.remove('selected'));
                e.target.closest('.format-option').classList.add('selected');
            });
        });
    },

    async startConversion() {
        const url = this.elements.input?.value.trim();
        if (!url) { Toast.warning('Enter a URL first'); return; }

        const selectedFormat = this.state.formats.find(f => f.format_id === this.state.selectedFormat);
        const filesize = selectedFormat?.filesize_bytes || 0;

        this.setConvertLoading(true);
        this.state.progress = 0;
        Toast.info('Starting download...');

        try {
            const res = await fetch('/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    format_id: this.state.selectedFormat,
                    resolved_url: this.state.resolvedUrl,
                    cookies: this.state.cookies,
                    referer: this.state.referer,
                    fingerprint: this.state.fingerprint,
                    title: this.state.videoTitle,
                    filesize: filesize
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed');

            this.state.currentTaskId = data.task_id;
            if (this.state.pollInterval) clearInterval(this.state.pollInterval);
            this.state.pollInterval = setInterval(() => this.checkStatus(), 1500);
        } catch (e) {
            this.setConvertLoading(false);
            Toast.error(e.message);
        }
    },

    async checkStatus() {
        if (!this.state.currentTaskId) return;
        try {
            const res = await fetch(`/status/${this.state.currentTaskId}`);
            if (!res.ok) throw new Error('Network error');
            const data = await res.json();

            if (data.status === 'completed') {
                this.stopPolling();
                this.setConvertLoading(false);
                this.loadHistory();
                this.checkUsageLimit();
                Toast.success('Ready to download!');
            } else if (data.status === 'failed') {
                this.stopPolling();
                this.setConvertLoading(false);
                this.loadHistory();
                Toast.error(data.error || 'Download failed');
            }
        } catch (e) { console.error('Poll error:', e); }
    },

    stopPolling() {
        if (this.state.pollInterval) {
            clearInterval(this.state.pollInterval);
            this.state.pollInterval = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
