(function() {
    const redirectTo403 = () => { window.location.href = '/blocked'; };

    document.addEventListener('contextmenu', e => e.preventDefault());

    document.addEventListener('keydown', e => {
        if (e.key === 'F12' || 
            (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'i' || e.key === 'J' || e.key === 'j' || e.key === 'C' || e.key === 'c')) ||
            (e.ctrlKey && (e.key === 'U' || e.key === 'u' || e.key === 'S' || e.key === 's'))) {
            e.preventDefault();
            redirectTo403();
        }
    });

    let devtoolsOpen = false;
    const threshold = 160;

    const checkDevTools = () => {
        const widthThreshold = window.outerWidth - window.innerWidth > threshold;
        const heightThreshold = window.outerHeight - window.innerHeight > threshold;
        
        if (widthThreshold || heightThreshold) {
            if (!devtoolsOpen) {
                devtoolsOpen = true;
                redirectTo403();
            }
        } else {
            devtoolsOpen = false;
        }
    };

    setInterval(checkDevTools, 1000);

    const element = new Image();
    Object.defineProperty(element, 'id', {
        get: function() {
            redirectTo403();
        }
    });
    setInterval(() => { console.log(element); console.clear(); }, 1000);
})();
