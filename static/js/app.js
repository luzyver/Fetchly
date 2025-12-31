const App = {
    async init() {
        ThemeManager.init();
        UI.init();
        
        if (!UI.elements.input) return;

        AppState.fingerprint = Utils.generateFingerprint();
        
        this.bindEvents();
        UI.checkInputState();
        await this.checkUsageLimit();
        await this.loadHistory();
    },

    bindEvents() {
        const { input, pasteBtn, clearBtn, fetchBtn, convertBtn } = UI.elements;

        input?.addEventListener('input', () => {
            UI.checkInputState();
            this.resetFormatSelection();
        });

        input?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !AppState.isProcessing) {
                AppState.formats.length > 0 ? this.startConversion() : this.fetchFormats();
            }
        });

        pasteBtn?.addEventListener('click', () => this.handlePaste());
        clearBtn?.addEventListener('click', () => this.handleClear());
        fetchBtn?.addEventListener('click', () => this.fetchFormats());
        convertBtn?.addEventListener('click', () => this.startConversion());
    },

    async handlePaste() {
        try {
            const text = await navigator.clipboard.readText();
            UI.setInputValue(text);
            UI.checkInputState();
            this.resetFormatSelection();
            Toast.success('URL pasted');
        } catch {
            Toast.error('Clipboard access denied');
        }
    },

    handleClear() {
        UI.setInputValue('');
        UI.checkInputState();
        this.resetFormatSelection();
        UI.focusInput();
    },

    resetFormatSelection() {
        AppState.reset();
        UI.hideFormatSection();
    },

    async checkUsageLimit() {
        if (!AppState.fingerprint) return;
        
        try {
            const { data } = await API.checkLimit(AppState.fingerprint);
            UI.renderUsage(data);
            
            if (data.captcha_enabled && data.turnstile_site_key) {
                CaptchaManager.init(data.turnstile_site_key);
            }
        } catch (e) {
            console.error('Failed to check limit:', e);
        }
    },

    async loadHistory() {
        if (!AppState.fingerprint) return;
        
        try {
            const { data } = await API.loadHistory(AppState.fingerprint);
            UI.renderHistory(data.history || []);
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    },

    async fetchFormats() {
        const url = UI.getInputValue();
        
        if (!url) {
            Toast.warning('Enter a URL first');
            UI.focusInput();
            return;
        }
        
        if (!Utils.isValidUrl(url)) {
            Toast.warning('Enter a valid URL');
            return;
        }

        UI.setFetchLoading(true);
        Toast.info('Fetching formats...');

        try {
            const captchaToken = CaptchaManager.getToken();
            const { response, data } = await API.fetchFormats(url, captchaToken);
            
            if (data.captcha_required) {
                CaptchaManager.reset();
                throw new Error(data.error || 'Verification failed');
            }
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch');
            }

            AppState.setFormats(data);
            UI.showFormatSection();
            UI.renderFormats(AppState.formats, AppState.videoTitle);
            Toast.success(`Found ${AppState.formats.length} formats`);
        } catch (e) {
            Toast.error(e.message);
        } finally {
            UI.setFetchLoading(false);
        }
    },

    async startConversion() {
        const url = UI.getInputValue();
        if (!url) {
            Toast.warning('Enter a URL first');
            return;
        }

        const selectedFormat = AppState.formats.find(f => f.format_id === AppState.selectedFormat);
        
        UI.setConvertLoading(true);
        AppState.progress = 0;
        Toast.info('Starting download...');

        try {
            const { response, data } = await API.startConversion({
                url,
                format_id: AppState.selectedFormat,
                resolved_url: AppState.resolvedUrl,
                cookies: AppState.cookies,
                referer: AppState.referer,
                fingerprint: AppState.fingerprint,
                title: AppState.videoTitle,
                filesize: selectedFormat?.filesize_bytes || 0
            });

            if (!response.ok) {
                throw new Error(data.error || 'Failed');
            }

            AppState.currentTaskId = data.task_id;
            this.startPolling();
        } catch (e) {
            UI.setConvertLoading(false);
            Toast.error(e.message);
        }
    },

    startPolling() {
        this.stopPolling();
        AppState.pollInterval = setInterval(() => this.checkStatus(), 1500);
    },

    stopPolling() {
        if (AppState.pollInterval) {
            clearInterval(AppState.pollInterval);
            AppState.pollInterval = null;
        }
    },

    async checkStatus() {
        if (!AppState.currentTaskId) return;
        
        try {
            const { response, data } = await API.checkStatus(AppState.currentTaskId);
            
            if (!response.ok) {
                throw new Error('Network error');
            }

            if (data.status === 'completed') {
                this.handleConversionComplete();
            } else if (data.status === 'failed') {
                this.handleConversionFailed(data.error);
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    },

    handleConversionComplete() {
        this.stopPolling();
        UI.setConvertLoading(false);
        this.loadHistory();
        this.checkUsageLimit();
        Toast.success('Ready to download!');
    },

    handleConversionFailed(error) {
        this.stopPolling();
        UI.setConvertLoading(false);
        this.loadHistory();
        Toast.error(error || 'Download failed');
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
