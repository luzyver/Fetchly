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
        fingerprint: null
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
            videoTitle: document.getElementById('videoTitle'),
            statusCard: document.getElementById('statusCard'),
            statusIcon: document.getElementById('statusIcon'),
            statusTitle: document.getElementById('statusTitle'),
            statusMessage: document.getElementById('statusMessage'),
            progressContainer: document.getElementById('progressContainer'),
            progressBar: document.getElementById('progressBar'),
            progressText: document.getElementById('progressText'),
            actionArea: document.getElementById('actionArea'),
            downloadBtn: document.getElementById('downloadBtn'),
            errorArea: document.getElementById('errorArea'),
            errorDetails: document.getElementById('errorDetails'),
            usageInfo: document.getElementById('usageInfo'),
            historySection: document.getElementById('historySection'),
            historyList: document.getElementById('historyList'),
            historyEmpty: document.getElementById('historyEmpty')
        };

        if (!this.elements.input) return;

        await this.initFingerprint();
        this.bindEvents();
        this.checkInputState();
        this.checkUsageLimit();
        this.loadHistory();
    },

    async initFingerprint() {
        try {
            if (typeof Fingerprint !== 'undefined') {
                const fp = await Fingerprint.load();
                const result = await fp.get();
                this.state.fingerprint = result.visitorId;
            } else {
                this.state.fingerprint = this.generateFallbackFingerprint();
            }
        } catch {
            this.state.fingerprint = this.generateFallbackFingerprint();
        }
    },

    generateFallbackFingerprint() {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillText('fingerprint', 2, 2);
        const data = canvas.toDataURL() + navigator.userAgent + screen.width + screen.height + new Date().getTimezoneOffset();
        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            hash = ((hash << 5) - hash) + data.charCodeAt(i);
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
        } catch (e) {
            console.error('Failed to check limit:', e);
        }
    },

    updateUsageDisplay(data) {
        const usedMB = Math.round(data.used / (1024 * 1024));
        const limitMB = Math.round(data.limit / (1024 * 1024));
        const remainingMB = Math.round(data.remaining / (1024 * 1024));
        const percent = Math.round((data.used / data.limit) * 100);

        if (this.elements.usageInfo) {
            this.elements.usageInfo.innerHTML = `
                <div class="text-xs text-gray-500">
                    Daily usage: ${usedMB}MB / ${limitMB}MB (${remainingMB}MB remaining)
                </div>
                <div class="h-1 bg-dark-700 rounded-full overflow-hidden mt-1">
                    <div class="h-full ${percent > 80 ? 'bg-red-500' : 'bg-accent-500'} rounded-full" style="width: ${percent}%"></div>
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
            this.elements.historySection.classList.add('hidden');
            return;
        }

        this.elements.historySection.classList.remove('hidden');
        this.elements.historyEmpty?.classList.add('hidden');
        this.elements.historyList?.classList.remove('hidden');

        const formatSize = (bytes) => {
            if (!bytes) return '-';
            if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
            if (bytes > 1024) return `${(bytes / 1024).toFixed(1)}KB`;
            return `${bytes}B`;
        };

        const statusColors = {
            completed: 'text-emerald-400',
            failed: 'text-red-400',
            processing: 'text-accent-400',
            queued: 'text-gray-400'
        };

        const statusIcons = {
            completed: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
            failed: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
            processing: '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>',
            queued: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
        };

        this.elements.historyList.innerHTML = history.map(item => `
            <div class="flex items-center gap-3 p-3 rounded-lg bg-dark-800/30 border border-white/5">
                <div class="${statusColors[item.status] || 'text-gray-400'}">
                    ${statusIcons[item.status] || statusIcons.queued}
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm text-white truncate">${item.title || 'Video'}</p>
                    <p class="text-xs text-gray-500">${formatSize(item.filesize)}</p>
                </div>
                ${item.status === 'completed' ? `
                    <a href="/download/${item.id}?fingerprint=${this.state.fingerprint}" 
                       class="p-2 text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-all" title="Download">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                        </svg>
                    </a>
                ` : ''}
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
        this.elements.statusCard?.classList.add('hidden');
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

    async fetchFormats() {
        const url = this.elements.input?.value.trim();
        if (!url) { Toast.warning('Enter a URL first'); this.elements.input?.focus(); return; }
        if (!url.startsWith('http')) { Toast.warning('Enter a valid URL'); return; }

        this.setFetchLoading(true);
        this.elements.statusCard?.classList.add('hidden');
        Toast.info('Fetching formats...');

        try {
            const res = await fetch('/fetch-formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to fetch');

            Object.assign(this.state, {
                formats: data.formats || [],
                resolvedUrl: data.resolved_url,
                cookies: data.cookies,
                referer: data.referer,
                videoTitle: data.title
            });

            this.renderFormatSelection();
            Toast.success(`Found ${this.state.formats.length} formats`);
        } catch (e) {
            Toast.error(e.message);
            this.elements.statusCard?.classList.remove('hidden');
            this.updateStatusUI('failed', e.message);
        } finally {
            this.setFetchLoading(false);
        }
    },

    renderFormatSelection() {
        if (!this.elements.formatSection || !this.elements.formatList) return;

        this.elements.formatSection.classList.remove('hidden');
        this.elements.fetchBtn?.classList.add('hidden');
        this.elements.convertBtn?.classList.remove('hidden');

        if (this.elements.videoTitle && this.state.videoTitle) {
            this.elements.videoTitle.textContent = this.state.videoTitle;
            this.elements.videoTitle.title = this.state.videoTitle;
        }

        this.elements.formatList.innerHTML = this.state.formats.map((fmt, i) => {
            const isBest = fmt.format_id === 'best';
            return `
                <label class="format-option flex items-center gap-3 p-3 rounded-lg border transition-all ${i === 0 ? 'bg-accent-500/10 border-accent-500/30' : 'bg-dark-800/30 border-white/5 hover:bg-dark-800/50'}">
                    <input type="radio" name="format" value="${fmt.format_id}" ${i === 0 ? 'checked' : ''} class="w-4 h-4">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-semibold text-white">${fmt.resolution}</span>
                            ${isBest ? '<span class="px-1.5 py-0.5 text-[10px] font-bold uppercase bg-accent-500/20 text-accent-400 rounded">Best</span>' : ''}
                            ${!fmt.has_audio && !isBest ? '<span class="px-1.5 py-0.5 text-[10px] font-bold uppercase bg-yellow-500/20 text-yellow-400 rounded">No Audio</span>' : ''}
                        </div>
                        <div class="flex items-center gap-2 mt-0.5 text-[11px] text-gray-500">
                            ${fmt.filesize ? `<span>${fmt.filesize}</span>` : ''}
                            ${fmt.bitrate ? `<span>• ${fmt.bitrate}</span>` : ''}
                            ${!isBest ? `<span>• ${fmt.ext.toUpperCase()}</span>` : ''}
                        </div>
                    </div>
                </label>`;
        }).join('');

        this.elements.formatList.querySelectorAll('input[name="format"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.state.selectedFormat = e.target.value;
                this.elements.formatList.querySelectorAll('.format-option').forEach(opt => {
                    opt.classList.remove('bg-accent-500/10', 'border-accent-500/30');
                    opt.classList.add('bg-dark-800/30', 'border-white/5');
                });
                e.target.closest('.format-option').classList.remove('bg-dark-800/30', 'border-white/5');
                e.target.closest('.format-option').classList.add('bg-accent-500/10', 'border-accent-500/30');
            });
        });
    },

    async startConversion() {
        const url = this.elements.input?.value.trim();
        if (!url) { Toast.warning('Enter a URL first'); return; }

        this.setConvertLoading(true);
        this.state.progress = 0;
        this.elements.statusCard?.classList.add('hidden');
        this.elements.errorArea?.classList.add('hidden');
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
                    title: this.state.videoTitle
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed');

            this.state.currentTaskId = data.task_id;
            this.elements.statusCard?.classList.remove('hidden');
            this.updateStatusUI('processing');

            if (this.state.pollInterval) clearInterval(this.state.pollInterval);
            this.state.pollInterval = setInterval(() => this.checkStatus(), 1500);
        } catch (e) {
            this.setConvertLoading(false);
            this.elements.statusCard?.classList.remove('hidden');
            this.updateStatusUI('failed', e.message);
            Toast.error(e.message);
        }
    },

    async checkStatus() {
        if (!this.state.currentTaskId) return;
        try {
            const res = await fetch(`/status/${this.state.currentTaskId}`);
            if (!res.ok) throw new Error('Network error');
            const data = await res.json();

            data.progress !== undefined ? this.updateProgress(data.progress) : this.simulateProgress();

            if (data.status === 'completed') {
                this.stopPolling();
                this.updateProgress(100);
                this.updateStatusUI('completed');
                this.setConvertLoading(false);
                this.loadHistory();
                Toast.success('Ready to download!');
            } else if (data.status === 'failed') {
                this.stopPolling();
                this.updateStatusUI('failed', data.error);
                this.setConvertLoading(false);
                this.loadHistory();
                Toast.error('Download failed');
            }
        } catch (e) { console.error('Poll error:', e); }
    },

    simulateProgress() {
        if (this.state.progress < 90) {
            this.state.progress = Math.min(90, this.state.progress + Math.random() * 5 + 1);
            this.updateProgress(this.state.progress);
        }
    },

    updateProgress(percent) {
        this.state.progress = percent;
        if (this.elements.progressBar) this.elements.progressBar.style.width = `${percent}%`;
        if (this.elements.progressText) this.elements.progressText.textContent = `${Math.round(percent)}%`;
    },

    stopPolling() {
        if (this.state.pollInterval) {
            clearInterval(this.state.pollInterval);
            this.state.pollInterval = null;
        }
    },

    updateStatusUI(status, message = '') {
        const icons = {
            processing: `<div class="rounded-full bg-accent-500/10 p-3 ring-2 ring-accent-500/20 glow-accent">
                <svg class="h-6 w-6 text-accent-400 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>`,
            completed: `<div class="rounded-full bg-emerald-500/10 p-3 ring-2 ring-emerald-500/20 glow-success">
                <svg class="h-6 w-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
            </div>`,
            failed: `<div class="rounded-full bg-red-500/10 p-3 ring-2 ring-red-500/20 glow-error">
                <svg class="h-6 w-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </div>`
        };

        if (this.elements.statusIcon) this.elements.statusIcon.innerHTML = icons[status] || icons.processing;

        if (status === 'processing') {
            const isAudio = this.state.selectedFormat === 'tiktok_audio';
            this.elements.statusTitle && (this.elements.statusTitle.textContent = 'Processing...');
            this.elements.statusMessage && (this.elements.statusMessage.textContent = isAudio ? 'Downloading audio...' : 'Downloading and converting to MP4');
            this.elements.progressContainer?.classList.remove('hidden');
            this.elements.actionArea?.classList.add('hidden');
            this.elements.errorArea?.classList.add('hidden');
        } else if (status === 'completed') {
            const isAudio = this.state.selectedFormat === 'tiktok_audio';
            this.elements.statusTitle && (this.elements.statusTitle.textContent = 'Ready!');
            this.elements.statusMessage && (this.elements.statusMessage.textContent = isAudio ? 'Your audio is ready for download' : 'Your video is ready for download');
            this.elements.progressContainer?.classList.add('hidden');
            this.elements.actionArea?.classList.remove('hidden');
            this.elements.errorArea?.classList.add('hidden');
            if (this.elements.downloadBtn) {
                this.elements.downloadBtn.href = `/download/${this.state.currentTaskId}?fingerprint=${this.state.fingerprint}`;
                this.elements.downloadBtn.onclick = () => {
                    setTimeout(() => {
                        this.checkUsageLimit();
                        this.loadHistory();
                    }, 1000);
                };
            }
            const btnText = document.getElementById('downloadBtnText');
            if (btnText) btnText.textContent = isAudio ? 'Download MP3' : 'Download MP4';
        } else if (status === 'failed') {
            this.elements.statusTitle && (this.elements.statusTitle.textContent = 'Failed');
            this.elements.statusMessage && (this.elements.statusMessage.textContent = 'Something went wrong');
            this.elements.progressContainer?.classList.add('hidden');
            this.elements.actionArea?.classList.add('hidden');
            this.elements.errorArea?.classList.remove('hidden');
            if (this.elements.errorDetails) this.elements.errorDetails.textContent = message || 'Unknown error';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());