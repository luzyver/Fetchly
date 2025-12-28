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
        videoTitle: null
    },

    elements: {},

    init() {
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
            errorDetails: document.getElementById('errorDetails')
        };

        if (!this.elements.input) {
            console.error('App: URL input not found');
            return;
        }

        this.bindEvents();
        this.checkInputState();
    },

    bindEvents() {
        this.elements.input.addEventListener('input', () => {
            this.checkInputState();
            this.resetFormatSelection();
        });

        this.elements.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.state.isProcessing) {
                if (this.state.formats.length > 0) {
                    this.startConversion();
                } else {
                    this.fetchFormats();
                }
            }
        });

        if (this.elements.pasteBtn) {
            this.elements.pasteBtn.addEventListener('click', async () => {
                try {
                    const text = await navigator.clipboard.readText();
                    this.elements.input.value = text;
                    this.checkInputState();
                    this.resetFormatSelection();
                    Toast.success('URL pasted from clipboard');
                } catch (err) {
                    Toast.error('Failed to access clipboard');
                }
            });
        }

        if (this.elements.clearBtn) {
            this.elements.clearBtn.addEventListener('click', () => {
                this.elements.input.value = '';
                this.checkInputState();
                this.resetFormatSelection();
                this.elements.input.focus();
            });
        }

        if (this.elements.fetchBtn) {
            this.elements.fetchBtn.addEventListener('click', () => {
                this.fetchFormats();
            });
        }

        if (this.elements.convertBtn) {
            this.elements.convertBtn.addEventListener('click', () => this.startConversion());
        }
    },

    checkInputState() {
        const hasValue = this.elements.input.value.trim().length > 0;
        if (this.elements.clearBtn) {
            this.elements.clearBtn.classList.toggle('hidden', !hasValue);
        }
        if (this.elements.pasteBtn) {
            this.elements.pasteBtn.classList.toggle('hidden', hasValue);
        }
    },

    resetFormatSelection() {
        this.state.formats = [];
        this.state.selectedFormat = 'best';
        this.state.resolvedUrl = null;
        this.state.cookies = null;
        this.state.referer = null;
        this.state.videoTitle = null;

        if (this.elements.formatSection) {
            this.elements.formatSection.classList.add('hidden');
        }
        if (this.elements.convertBtn) {
            this.elements.convertBtn.classList.add('hidden');
        }
        if (this.elements.fetchBtn) {
            this.elements.fetchBtn.classList.remove('hidden');
        }
        if (this.elements.statusCard) {
            this.elements.statusCard.classList.add('hidden');
        }
    },

    setFetchLoading(isLoading) {
        if (!this.elements.fetchBtn) return;

        this.elements.fetchBtn.disabled = isLoading;
        if (this.elements.input) this.elements.input.disabled = isLoading;

        if (this.elements.fetchContent && this.elements.fetchLoader) {
            if (isLoading) {
                this.elements.fetchContent.classList.add('hidden');
                this.elements.fetchLoader.classList.remove('hidden');
            } else {
                this.elements.fetchContent.classList.remove('hidden');
                this.elements.fetchLoader.classList.add('hidden');
            }
        }
    },

    setConvertLoading(isLoading) {
        this.state.isProcessing = isLoading;
        if (!this.elements.convertBtn) return;

        this.elements.convertBtn.disabled = isLoading;
        if (this.elements.input) this.elements.input.disabled = isLoading;

        if (this.elements.btnContent && this.elements.btnLoader) {
            if (isLoading) {
                this.elements.btnContent.classList.add('hidden');
                this.elements.btnLoader.classList.remove('hidden');
            } else {
                this.elements.btnContent.classList.remove('hidden');
                this.elements.btnLoader.classList.add('hidden');
            }
        }
    },

    async fetchFormats() {
        const url = this.elements.input?.value.trim();

        if (!url) {
            Toast.warning('Please enter a URL first');
            this.elements.input?.focus();
            return;
        }

        if (!url.startsWith('http')) {
            Toast.warning('Please enter a valid URL');
            return;
        }

        this.setFetchLoading(true);
        if (this.elements.statusCard) {
            this.elements.statusCard.classList.add('hidden');
        }
        Toast.info('Fetching available formats...');

        try {
            const response = await fetch('/fetch-formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch formats');
            }

            this.state.formats = data.formats || [];
            this.state.resolvedUrl = data.resolved_url;
            this.state.cookies = data.cookies;
            this.state.referer = data.referer;
            this.state.videoTitle = data.title;

            this.renderFormatSelection();
            Toast.success(`Found ${this.state.formats.length} formats`);

        } catch (error) {
            Toast.error(error.message || 'Failed to fetch formats');
            if (this.elements.statusCard) {
                this.elements.statusCard.classList.remove('hidden');
            }
            this.updateStatusUI('failed', error.message);
        } finally {
            this.setFetchLoading(false);
        }
    },

    renderFormatSelection() {
        if (!this.elements.formatSection || !this.elements.formatList) return;

        this.elements.formatSection.classList.remove('hidden');
        this.elements.formatSection.classList.add('animate-scale-in');

        if (this.elements.fetchBtn) this.elements.fetchBtn.classList.add('hidden');
        if (this.elements.convertBtn) this.elements.convertBtn.classList.remove('hidden');

        if (this.elements.videoTitle && this.state.videoTitle) {
            this.elements.videoTitle.textContent = this.state.videoTitle;
            this.elements.videoTitle.title = this.state.videoTitle;
        }

        let html = '';
        this.state.formats.forEach((fmt, index) => {
            const isSelected = index === 0;
            const isBest = fmt.format_id === 'best';

            html += `
                <label class="format-option flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all border ${isSelected ? 'bg-brand-500/10 border-brand-500/30' : 'bg-slate-800/30 border-slate-700/30 hover:bg-slate-800/50'}">
                    <input type="radio" name="format" value="${fmt.format_id}" ${isSelected ? 'checked' : ''}
                        class="w-4 h-4 text-brand-500 bg-slate-700 border-slate-600 focus:ring-brand-500 focus:ring-2">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-semibold text-white">${fmt.resolution}</span>
                            ${isBest ? '<span class="px-1.5 py-0.5 text-[10px] font-bold uppercase bg-brand-500/20 text-brand-400 rounded">Recommended</span>' : ''}
                            ${!fmt.has_audio && !isBest ? '<span class="px-1.5 py-0.5 text-[10px] font-bold uppercase bg-yellow-500/20 text-yellow-400 rounded">No Audio</span>' : ''}
                        </div>
                        <div class="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500">
                            ${fmt.filesize ? `<span>${fmt.filesize}</span>` : ''}
                            ${fmt.bitrate ? `<span>• ${fmt.bitrate}</span>` : ''}
                            ${!isBest ? `<span>• ${fmt.ext.toUpperCase()}</span>` : ''}
                        </div>
                    </div>
                </label>
            `;
        });

        this.elements.formatList.innerHTML = html;

        this.elements.formatList.querySelectorAll('input[name="format"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.state.selectedFormat = e.target.value;
                this.elements.formatList.querySelectorAll('.format-option').forEach(opt => {
                    opt.classList.remove('bg-brand-500/10', 'border-brand-500/30');
                    opt.classList.add('bg-slate-800/30', 'border-slate-700/30');
                });
                e.target.closest('.format-option').classList.remove('bg-slate-800/30', 'border-slate-700/30');
                e.target.closest('.format-option').classList.add('bg-brand-500/10', 'border-brand-500/30');
            });
        });
    },

    async startConversion() {
        const url = this.elements.input?.value.trim();

        if (!url) {
            Toast.warning('Please enter a URL first');
            return;
        }

        this.setConvertLoading(true);
        this.state.progress = 0;
        if (this.elements.statusCard) this.elements.statusCard.classList.add('hidden');
        if (this.elements.errorArea) this.elements.errorArea.classList.add('hidden');

        Toast.info('Starting conversion...');

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    format_id: this.state.selectedFormat,
                    resolved_url: this.state.resolvedUrl,
                    cookies: this.state.cookies,
                    referer: this.state.referer
                })
            });

            const data = await response.json();

            if (!response.ok) throw new Error(data.error || 'Failed to start conversion');

            this.state.currentTaskId = data.task_id;
            if (this.elements.statusCard) {
                this.elements.statusCard.classList.remove('hidden');
                this.elements.statusCard.classList.add('animate-scale-in');
            }
            this.updateStatusUI('processing');

            if (this.state.pollInterval) clearInterval(this.state.pollInterval);
            this.state.pollInterval = setInterval(() => this.checkStatus(), 1500);

        } catch (error) {
            this.setConvertLoading(false);
            if (this.elements.statusCard) this.elements.statusCard.classList.remove('hidden');
            this.updateStatusUI('failed', error.message);
            Toast.error(error.message || 'Conversion failed');
        }
    },

    async checkStatus() {
        if (!this.state.currentTaskId) return;

        try {
            const response = await fetch(`/status/${this.state.currentTaskId}`);
            if (!response.ok) throw new Error('Network error');

            const data = await response.json();

            if (data.progress !== undefined) {
                this.updateProgress(data.progress);
            } else {
                this.simulateProgress();
            }

            if (data.status === 'completed') {
                this.stopPolling();
                this.updateProgress(100);
                this.updateStatusUI('completed');
                this.setConvertLoading(false);
                Toast.success('Video ready for download!');
            } else if (data.status === 'failed') {
                this.stopPolling();
                this.updateStatusUI('failed', data.error);
                this.setConvertLoading(false);
                Toast.error('Conversion failed');
            }
        } catch (error) {
            console.error('Poll error:', error);
        }
    },

    simulateProgress() {
        if (this.state.progress < 90) {
            const increment = Math.random() * 5 + 1;
            this.state.progress = Math.min(90, this.state.progress + increment);
            this.updateProgress(this.state.progress);
        }
    },

    updateProgress(percent) {
        this.state.progress = percent;
        if (this.elements.progressBar) {
            this.elements.progressBar.style.width = `${percent}%`;
        }
        if (this.elements.progressText) {
            this.elements.progressText.textContent = `${Math.round(percent)}%`;
        }
    },

    stopPolling() {
        if (this.state.pollInterval) {
            clearInterval(this.state.pollInterval);
            this.state.pollInterval = null;
        }
    },

    updateStatusUI(status, message = '') {
        const icons = {
            processing: `<div class="rounded-full bg-brand-500/10 p-3 ring-2 ring-brand-500/20 glow-brand">
                <svg class="h-6 w-6 text-brand-500 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>`,
            completed: `<div class="rounded-full bg-emerald-500/10 p-3 ring-2 ring-emerald-500/20 glow-success animate-bounce-in">
                <svg class="h-6 w-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
            </div>`,
            failed: `<div class="rounded-full bg-red-500/10 p-3 ring-2 ring-red-500/20 glow-error">
                <svg class="h-6 w-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </div>`
        };

        if (this.elements.statusIcon) {
            this.elements.statusIcon.innerHTML = icons[status] || icons.processing;
        }

        if (status === 'processing') {
            if (this.elements.statusTitle) this.elements.statusTitle.textContent = 'Processing Stream...';
            if (this.elements.statusMessage) this.elements.statusMessage.textContent = 'Downloading and converting to MP4.';
            if (this.elements.progressContainer) this.elements.progressContainer.classList.remove('hidden');
            if (this.elements.actionArea) this.elements.actionArea.classList.add('hidden');
            if (this.elements.errorArea) this.elements.errorArea.classList.add('hidden');
        } else if (status === 'completed') {
            if (this.elements.statusTitle) this.elements.statusTitle.textContent = 'Ready for Download';
            if (this.elements.statusMessage) this.elements.statusMessage.textContent = 'Your video has been converted successfully.';
            if (this.elements.progressContainer) this.elements.progressContainer.classList.add('hidden');
            if (this.elements.actionArea) {
                this.elements.actionArea.classList.remove('hidden');
                this.elements.actionArea.classList.add('animate-scale-in');
            }
            if (this.elements.errorArea) this.elements.errorArea.classList.add('hidden');
            if (this.elements.downloadBtn) this.elements.downloadBtn.href = `/download/${this.state.currentTaskId}`;
        } else if (status === 'failed') {
            if (this.elements.statusTitle) this.elements.statusTitle.textContent = 'Conversion Failed';
            if (this.elements.statusMessage) this.elements.statusMessage.textContent = 'Something went wrong while processing.';
            if (this.elements.progressContainer) this.elements.progressContainer.classList.add('hidden');
            if (this.elements.actionArea) this.elements.actionArea.classList.add('hidden');
            if (this.elements.errorArea) {
                this.elements.errorArea.classList.remove('hidden');
                this.elements.errorArea.classList.add('animate-scale-in');
            }
            if (this.elements.errorDetails) this.elements.errorDetails.textContent = message || 'Unknown server error.';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());