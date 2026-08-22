/**
 * CampusGuard AI - Parent Portal JavaScript
 * Mobile Navigation, Modal Management, Tab Filtering, Password Toggles & Charting
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Sidebar Navigation Drawer
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('parent-sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    if (mobileMenuBtn && sidebar && sidebarOverlay) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('active');
        });

        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // 2. Password Visibility Toggle Helper
    const togglePwButtons = document.querySelectorAll('.toggle-password-btn');
    togglePwButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                if (input.type === 'password') {
                    input.type = 'text';
                    btn.textContent = '👁️‍🗨️';
                } else {
                    input.type = 'password';
                    btn.textContent = '👁️';
                }
            }
        });
    });

    // 3. Tab Switching for Day Timetables and Filter Views
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetGroup = btn.getAttribute('data-group');
            const targetContentId = btn.getAttribute('data-target');

            // Deactivate siblings
            document.querySelectorAll(`.tab-btn[data-group="${targetGroup}"]`).forEach(b => b.classList.remove('active'));
            document.querySelectorAll(`.tab-pane[data-group="${targetGroup}"]`).forEach(pane => pane.classList.remove('active'));

            // Activate current
            btn.classList.add('active');
            const activePane = document.getElementById(targetContentId);
            if (activePane) {
                activePane.classList.add('active');
            }
        });
    });
});

// Modal Helpers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Global modal overlay click-to-close
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});
