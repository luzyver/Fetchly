const CaptchaManager = {
    init(siteKey) {
        if (!siteKey || document.getElementById('turnstile-script')) return;
        
        AppState.captchaEnabled = true;
        AppState.turnstileSiteKey = siteKey;
        
        this.updateStatus('Verifying...', false);
        this.loadScript();
    },

    loadScript() {
        const script = document.createElement('script');
        script.id = 'turnstile-script';
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoad';
        script.async = true;

        window.onTurnstileLoad = () => this.renderWidget();
        document.head.appendChild(script);
    },

    renderWidget() {
        const container = document.createElement('div');
        container.id = 'turnstile-container';
        container.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: -1; opacity: 0; pointer-events: none;';
        document.body.appendChild(container);

        AppState.turnstileWidgetId = turnstile.render('#turnstile-container', {
            sitekey: AppState.turnstileSiteKey,
            theme: 'dark',
            size: 'invisible',
            callback: (token) => {
                AppState.turnstileToken = token;
                this.updateStatus('Verified', true);
            }
        });
    },

    updateStatus(text, verified) {
        const statusEl = document.getElementById('captchaStatus');
        const textEl = document.getElementById('captchaText');
        
        if (!statusEl || !textEl) return;
        
        statusEl.classList.remove('hidden');
        textEl.textContent = text;
        
        statusEl.classList.toggle('text-emerald-500', verified);
        statusEl.classList.toggle('text-[var(--text-muted)]', !verified);
    },

    getToken() {
        return AppState.captchaEnabled ? (AppState.turnstileToken || '') : '';
    },

    reset() {
        if (AppState.turnstileWidgetId !== null && typeof turnstile !== 'undefined') {
            turnstile.reset(AppState.turnstileWidgetId);
            AppState.turnstileToken = null;
            this.updateStatus('Verifying...', false);
        }
    }
};

window.CaptchaManager = CaptchaManager;
