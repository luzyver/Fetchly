(function() {
    const redirect = () => { 
        if (!window.location.pathname.includes('/devtools') && !window.location.pathname.includes('/admin')) {
            window.location.replace('/devtools'); 
        }
    };

    document.addEventListener('contextmenu', e => e.preventDefault());

    document.addEventListener('keydown', e => {
        if (e.key === 'F12' || 
            (e.ctrlKey && e.shiftKey && ['I','i','J','j','C','c'].includes(e.key)) ||
            (e.ctrlKey && ['U','u','S','s'].includes(e.key)) ||
            (e.metaKey && e.altKey && ['I','i','J','j','C','c'].includes(e.key))) {
            e.preventDefault();
            redirect();
        }
    });

    let isDevToolsOpen = false;

    const detectBySize = () => {
        const threshold = 160;
        const widthDiff = window.outerWidth - window.innerWidth > threshold;
        const heightDiff = window.outerHeight - window.innerHeight > threshold;
        return widthDiff || heightDiff;
    };

    const detectByDebugger = () => {
        let detected = false;
        const start = new Date();
        debugger;
        const end = new Date();
        if (end - start > 100) {
            detected = true;
        }
        return detected;
    };

    const detectByConsoleLog = () => {
        let detected = false;
        const img = new Image();
        Object.defineProperty(img, 'id', {
            get: function() {
                detected = true;
            }
        });
        console.log(img);
        console.clear();
        return detected;
    };

    const detectByToString = () => {
        let detected = false;
        const div = document.createElement('div');
        Object.defineProperty(div, 'id', {
            get: function() {
                detected = true;
            }
        });
        console.log(div);
        console.clear();
        return detected;
    };

    const detectByRegex = () => {
        let detected = false;
        const re = /./;
        re.toString = function() {
            detected = true;
            return '';
        };
        console.log(re);
        console.clear();
        return detected;
    };

    const detectByDate = () => {
        let detected = false;
        const date = new Date();
        date.toString = function() {
            detected = true;
            return '';
        };
        console.log(date);
        console.clear();
        return detected;
    };

    const detectByFunction = () => {
        let detected = false;
        const fn = function() {};
        fn.toString = function() {
            detected = true;
            return '';
        };
        console.log(fn);
        console.clear();
        return detected;
    };

    const detectByProfile = () => {
        let detected = false;
        const start = performance.now();
        for (let i = 0; i < 1000; i++) {
            console.log(i);
        }
        console.clear();
        const end = performance.now();
        if (end - start > 100) {
            detected = true;
        }
        return detected;
    };

    const detectMobileTools = () => {
        return typeof eruda !== 'undefined' || 
               typeof vConsole !== 'undefined' ||
               document.querySelector('#eruda') !== null ||
               document.querySelector('.eruda-container') !== null ||
               document.querySelector('#__vconsole') !== null;
    };

    const runAllDetections = () => {
        if (detectBySize() || 
            detectByConsoleLog() || 
            detectByToString() || 
            detectByRegex() ||
            detectByDate() ||
            detectByFunction() ||
            detectMobileTools()) {
            if (!isDevToolsOpen) {
                isDevToolsOpen = true;
                redirect();
            }
        }
    };

    setInterval(runAllDetections, 500);
    
    window.addEventListener('load', runAllDetections);
    document.addEventListener('DOMContentLoaded', runAllDetections);

    const noop = () => {};
    console.log = noop;
    console.warn = noop;
    console.error = noop;
    console.info = noop;
    console.debug = noop;
    console.table = noop;
    console.trace = noop;
    console.dir = noop;
    console.dirxml = noop;
    console.group = noop;
    console.groupEnd = noop;
    console.time = noop;
    console.timeEnd = noop;
    console.assert = noop;
    console.count = noop;
})();
