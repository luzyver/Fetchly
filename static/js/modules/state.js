const AppState = {
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
    turnstileSiteKey: '',
    turnstileWidgetId: null,
    turnstileToken: null,

    reset() {
        this.formats = [];
        this.selectedFormat = 'best';
        this.resolvedUrl = null;
        this.cookies = null;
        this.referer = null;
        this.videoTitle = null;
    },

    setFormats(data) {
        this.formats = data.formats || [];
        this.resolvedUrl = data.resolved_url;
        this.cookies = data.cookies;
        this.referer = data.referer;
        this.videoTitle = data.title;
    }
};

window.AppState = AppState;
