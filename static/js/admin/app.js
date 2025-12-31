const AdminApp = {
    init() {
        AdminUI.init();
        TabManager.init();
    }
};

document.addEventListener('DOMContentLoaded', () => AdminApp.init());
