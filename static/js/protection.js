(function() {
    const redirectTo403 = () => { 
        if (window.location.pathname !== '/devtools') {
            window.location.href = '/devtools'; 
        }
    };

    document.addEventListener('contextmenu', e => e.preventDefault());

    document.addEventListener('keydown', e => {
        if (e.key === 'F12' || 
            (e.ctrlKey && e.shiftKey && ['I','i','J','j','C','c'].includes(e.key)) ||
            (e.ctrlKey && ['U','u','S','s'].includes(e.key)) ||
            (e.metaKey && e.altKey && ['I','i','J','j','C','c'].includes(e.key))) {
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

    const detectDebugger = () => {
        const start = performance.now();
        debugger;
        const end = performance.now();
        if (end - start > 100) {
            redirectTo403();
        }
    };

    const checkConsole = () => {
        const element = new Image();
        let consoleOpened = false;
        Object.defineProperty(element, 'id', {
            get: function() {
                consoleOpened = true;
                redirectTo403();
            }
        });
        console.log('%c', element);
        console.clear();
        return consoleOpened;
    };

    const checkMobileDevTools = () => {
        if (typeof window.__REACT_DEVTOOLS_GLOBAL_HOOK__ !== 'undefined' ||
            typeof window.__VUE_DEVTOOLS_GLOBAL_HOOK__ !== 'undefined') {
            redirectTo403();
        }

        const userAgent = navigator.userAgent.toLowerCase();
        if (userAgent.includes('chrome') && !userAgent.includes('mobile')) {
            if (window.chrome && window.chrome.runtime) {
                return;
            }
        }

        if (/eruda|vconsole|devtools/i.test(navigator.userAgent)) {
            redirectTo403();
        }
    };

    const detectEruda = () => {
        if (typeof eruda !== 'undefined' || 
            document.querySelector('#eruda') ||
            document.querySelector('.eruda-container')) {
            redirectTo403();
        }
        
        if (typeof vConsole !== 'undefined' ||
            document.querySelector('#__vconsole')) {
            redirectTo403();
        }
    };

    const checkPerformance = () => {
        const t1 = performance.now();
        for (let i = 0; i < 100; i++) {
            console.log(i);
            console.clear();
        }
        const t2 = performance.now();
        if (t2 - t1 > 200) {
            redirectTo403();
        }
    };

    setInterval(checkDevTools, 1000);
    setInterval(checkConsole, 2000);
    setInterval(detectEruda, 2000);
    setInterval(checkMobileDevTools, 3000);

    window.addEventListener('load', () => {
        checkDevTools();
        checkConsole();
        detectEruda();
        checkMobileDevTools();
    });

    const originalConsoleLog = console.log;
    const originalConsoleWarn = console.warn;
    const originalConsoleError = console.error;
    
    let consoleCallCount = 0;
    const maxConsoleCalls = 10;
    
    const wrapConsole = (original) => {
        return function(...args) {
            consoleCallCount++;
            if (consoleCallCount > maxConsoleCalls) {
                return;
            }
            return original.apply(console, args);
        };
    };

    console.log = wrapConsole(originalConsoleLog);
    console.warn = wrapConsole(originalConsoleWarn);
    console.error = wrapConsole(originalConsoleError);

    setInterval(() => { consoleCallCount = 0; }, 5000);
})();
