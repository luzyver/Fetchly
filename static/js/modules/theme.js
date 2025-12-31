const ThemeManager = {
    init() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        this.apply(savedTheme);
        this.bindToggle();
    },

    apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.updateIcon(theme);
        this.updateMetaColor(theme);
    },

    toggle() {
        const current = document.documentElement.getAttribute('data-theme');
        const newTheme = current === 'light' ? 'dark' : 'light';
        this.apply(newTheme);
        localStorage.setItem('theme', newTheme);
    },

    updateIcon(theme) {
        const moon = document.getElementById('iconMoon');
        const sun = document.getElementById('iconSun');
        
        if (theme === 'light') {
            moon?.classList.add('hidden');
            sun?.classList.remove('hidden');
        } else {
            moon?.classList.remove('hidden');
            sun?.classList.add('hidden');
        }
    },

    updateMetaColor(theme) {
        const color = theme === 'light' ? '#ffffff' : '#141517';
        document.querySelector('meta[name="theme-color"]')?.setAttribute('content', color);
    },

    bindToggle() {
        document.getElementById('themeToggle')?.addEventListener('click', () => this.toggle());
    }
};

window.ThemeManager = ThemeManager;
