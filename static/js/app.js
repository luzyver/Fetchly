const App = {
    state: {
        currentTaskId: null,
        pollInterval: null,
        isProcessing: false
    },
    
    elements: {
        input: document.getElementById('url'),
        pasteBtn: document.getElementById('pasteBtn'),
        clearBtn: document.getElementById('clearBtn'),
        convertBtn: document.getElementById('convertBtn'),
        btnContent: document.getElementById('btnContent'),
        btnLoader: document.getElementById('btnLoader'),
        statusCard: document.getElementById('statusCard'),
        statusIcon: document.getElementById('statusIcon'),
        statusTitle: document.getElementById('statusTitle'),
        statusMessage: document.getElementById('statusMessage'),
        progressBar: document.getElementById('progressBar'),
        actionArea: document.getElementById('actionArea'),
        downloadBtn: document.getElementById('downloadBtn'),
        errorArea: document.getElementById('errorArea'),
        errorDetails: document.getElementById('errorDetails')
    },

    init() {
        if (!this.elements.input) return; // Guard if elements aren't present
        this.bindEvents();
        this.checkInputState();
    },

    bindEvents() {
        this.elements.input.addEventListener('input', () => this.checkInputState());
        
        this.elements.pasteBtn.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                this.elements.input.value = text;
                this.checkInputState();
            } catch (err) {
                console.error('Failed to read clipboard', err);
            }
        });

        this.elements.clearBtn.addEventListener('click', () => {
            this.elements.input.value = '';
            this.checkInputState();
            this.elements.input.focus();
        });
    },

    checkInputState() {
        const hasValue = this.elements.input.value.trim().length > 0;
        this.elements.clearBtn.classList.toggle('hidden', !hasValue);
        this.elements.pasteBtn.classList.toggle('hidden', hasValue);
    },

    setLoading(isLoading) {
        this.state.isProcessing = isLoading;
        this.elements.convertBtn.disabled = isLoading;
        this.elements.input.disabled = isLoading;
        
        if (isLoading) {
            this.elements.btnContent.classList.add('hidden');
            this.elements.btnLoader.classList.remove('hidden');
        } else {
            this.elements.btnContent.classList.remove('hidden');
            this.elements.btnLoader.classList.add('hidden');
            this.elements.input.disabled = false;
        }
    },

    async startConversion() {
        const url = this.elements.input.value.trim();
        
        if (!url) {
            alert('Please enter a URL');
            return;
        }

        this.setLoading(true);
        this.elements.statusCard.classList.add('hidden');
        this.elements.errorArea.classList.add('hidden');

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (!response.ok) throw new Error(data.error || 'Failed to start');

            this.state.currentTaskId = data.task_id;
            this.elements.statusCard.classList.remove('hidden');
            this.updateStatusUI('processing');

            if (this.state.pollInterval) clearInterval(this.state.pollInterval);
            this.state.pollInterval = setInterval(() => this.checkStatus(), 2000);

        } catch (error) {
            this.setLoading(false);
            this.elements.statusCard.classList.remove('hidden');
            this.updateStatusUI('failed', error.message);
        }
    },

    async checkStatus() {
        if (!this.state.currentTaskId) return;

        try {
            const response = await fetch(`/status/${this.state.currentTaskId}`);
            if (!response.ok) throw new Error('Network error');

            const data = await response.json();

            if (data.status === 'completed') {
                this.stopPolling();
                this.updateStatusUI('completed');
                this.setLoading(false);
            } else if (data.status === 'failed') {
                this.stopPolling();
                this.updateStatusUI('failed', data.error);
                this.setLoading(false);
            }
        } catch (error) {
            console.error('Poll error:', error);
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
            processing: `<div class="rounded-full bg-brand-500/10 p-2 ring-1 ring-brand-500/20"><svg class="h-6 w-6 text-brand-500 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div>`,
            completed: `<div class="rounded-full bg-emerald-500/10 p-2 ring-1 ring-emerald-500/20"><svg class="h-6 w-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></div>`,
            failed: `<div class="rounded-full bg-red-500/10 p-2 ring-1 ring-red-500/20"><svg class="h-6 w-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></div>`
        };

        this.elements.statusIcon.innerHTML = icons[status] || icons.processing;

        if (status === 'processing') {
            this.elements.statusTitle.textContent = 'Processing Stream...';
            this.elements.statusMessage.textContent = 'Analyzing source, downloading segments, and converting to MP4.';
            this.elements.progressBar.classList.remove('hidden');
            this.elements.actionArea.classList.add('hidden');
            this.elements.errorArea.classList.add('hidden');
        } else if (status === 'completed') {
            this.elements.statusTitle.textContent = 'Ready for Download';
            this.elements.statusMessage.textContent = 'Conversion finished successfully.';
            this.elements.progressBar.classList.add('hidden');
            this.elements.actionArea.classList.remove('hidden');
            this.elements.errorArea.classList.add('hidden');
            this.elements.downloadBtn.href = `/download/${this.state.currentTaskId}`;
        } else if (status === 'failed') {
            this.elements.statusTitle.textContent = 'Conversion Failed';
            this.elements.statusMessage.textContent = 'We encountered an error processing this URL.';
            this.elements.progressBar.classList.add('hidden');
            this.elements.actionArea.classList.add('hidden');
            this.elements.errorArea.classList.remove('hidden');
            this.elements.errorDetails.textContent = message || 'Unknown server error.';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
