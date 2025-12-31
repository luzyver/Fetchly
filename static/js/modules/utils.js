const Utils = {
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
            canvasData,
            navigator.userAgent,
            navigator.language,
            `${screen.width}x${screen.height}`,
            screen.colorDepth,
            new Date().getTimezoneOffset(),
            navigator.hardwareConcurrency || 0,
            navigator.deviceMemory || 0
        ].join('|');

        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            hash = ((hash << 5) - hash) + data.charCodeAt(i);
            hash = hash & hash;
        }
        return 'fp_' + Math.abs(hash).toString(16);
    },

    formatSize(bytes) {
        if (!bytes) return '-';
        if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
        if (bytes > 1024) return `${(bytes / 1024).toFixed(1)}KB`;
        return `${bytes}B`;
    },

    isValidUrl(url) {
        return url && url.startsWith('http');
    },

    truncate(text, maxLength = 50) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
};

window.Utils = Utils;
