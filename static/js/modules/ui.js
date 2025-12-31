const UI = {
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
            usageInfo: document.getElementById('usageInfo'),
            historyList: document.getElementById('historyList'),
            historyEmpty: document.getElementById('historyEmpty'),
            videoTitle: document.getElementById('videoTitle')
        };
    },

    getInputValue() {
        return this.elements.input?.value.trim() || '';
    },

    setInputValue(value) {
        if (this.elements.input) {
            this.elements.input.value = value;
        }
    },

    focusInput() {
        this.elements.input?.focus();
    },

    checkInputState() {
        const hasValue = this.getInputValue().length > 0;
        this.elements.clearBtn?.classList.toggle('hidden', !hasValue);
        this.elements.pasteBtn?.classList.toggle('hidden', hasValue);
    },

    setFetchLoading(loading) {
        const { fetchBtn, input, fetchContent, fetchLoader } = this.elements;
        if (!fetchBtn) return;
        
        fetchBtn.disabled = loading;
        if (input) input.disabled = loading;
        fetchContent?.classList.toggle('hidden', loading);
        fetchLoader?.classList.toggle('hidden', !loading);
    },

    setConvertLoading(loading) {
        AppState.isProcessing = loading;
        const { convertBtn, input, btnContent, btnLoader } = this.elements;
        if (!convertBtn) return;
        
        convertBtn.disabled = loading;
        if (input) input.disabled = loading;
        btnContent?.classList.toggle('hidden', loading);
        btnLoader?.classList.toggle('hidden', !loading);
    },

    showFormatSection() {
        this.elements.formatSection?.classList.remove('hidden');
        this.elements.fetchBtn?.classList.add('hidden');
        this.elements.convertBtn?.classList.remove('hidden');
    },

    hideFormatSection() {
        this.elements.formatSection?.classList.add('hidden');
        this.elements.convertBtn?.classList.add('hidden');
        this.elements.fetchBtn?.classList.remove('hidden');
    },

    renderUsage(data) {
        const usedMB = Math.round(data.used / (1024 * 1024));
        const limitMB = Math.round(data.limit / (1024 * 1024));
        const remainingMB = Math.round(data.remaining / (1024 * 1024));
        const percent = Math.round((data.used / data.limit) * 100);
        const barColor = percent > 80 ? 'bg-red-500' : 'bg-emerald-500';

        if (this.elements.usageInfo) {
            this.elements.usageInfo.innerHTML = `
                <div class="text-xs text-[var(--text-muted)]">
                    Daily usage: ${usedMB}MB / ${limitMB}MB (${remainingMB}MB remaining)
                </div>
                <div class="h-1 bg-[var(--border-subtle)] rounded-full overflow-hidden mt-1">
                    <div class="h-full ${barColor} rounded-full" style="width: ${percent}%"></div>
                </div>
            `;
        }
    },

    renderFormats(formats, title) {
        if (!this.elements.formatList) return;

        if (this.elements.videoTitle && title) {
            this.elements.videoTitle.textContent = title;
            this.elements.videoTitle.title = title;
        }

        this.elements.formatList.innerHTML = formats.map((fmt, i) => `
            <label class="format-option ${i === 0 ? 'selected' : ''}">
                <input type="radio" name="format" value="${fmt.format_id}" ${i === 0 ? 'checked' : ''} class="hidden">
                <div class="flex justify-between items-center w-full">
                    <span class="font-medium text-[var(--text-main)]">${fmt.resolution || 'Auto'}</span>
                </div>
                <div class="format-meta">
                    ${fmt.ext.toUpperCase()} ${fmt.filesize ? '• ' + fmt.filesize : ''}
                </div>
            </label>
        `).join('');

        this.bindFormatSelection();
    },

    bindFormatSelection() {
        this.elements.formatList?.querySelectorAll('input[name="format"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                AppState.selectedFormat = e.target.value;
                this.elements.formatList.querySelectorAll('.format-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                e.target.closest('.format-option').classList.add('selected');
            });
        });
    },

    renderHistory(history) {
        if (history.length === 0) {
            this.elements.historyEmpty?.classList.remove('hidden');
            if (this.elements.historyList) this.elements.historyList.innerHTML = '';
            return;
        }

        this.elements.historyEmpty?.classList.add('hidden');
        this.elements.historyList?.classList.remove('hidden');

        this.elements.historyList.innerHTML = history.map(item => `
            <div class="history-item">
                <div class="flex justify-between items-start">
                    <div class="history-title" title="${item.title || 'Unknown'}">${item.title || 'Untitled Video'}</div>
                    ${item.status === 'completed' 
                        ? `<a href="/download/${item.id}?fingerprint=${AppState.fingerprint}" class="text-xs text-[var(--text-main)] hover:underline">Download</a>` 
                        : `<span class="text-xs text-[var(--text-faint)]">${item.status}</span>`
                    }
                </div>
                <div class="history-meta mt-1">
                    <span class="status-dot ${this.getStatusClass(item.status)}"></span>
                    <span>${Utils.formatSize(item.filesize)}</span>
                    <span class="ml-auto font-mono text-[10px] text-[var(--text-faint)]">${item.id.substring(0, 6)}</span>
                </div>
            </div>
        `).join('');
    },

    getStatusClass(status) {
        const classes = {
            completed: 'success',
            failed: 'error'
        };
        return classes[status] || 'processing';
    }
};

window.UI = UI;
