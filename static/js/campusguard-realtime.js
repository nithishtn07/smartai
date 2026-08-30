/**
 * =============================================================================
 * CampusGuard AI — Universal Real-Time Engine & Live Notification Bell
 * =============================================================================
 * Supports WebSocket (Socket.IO) push and automatic REST polling fallback.
 */

(function () {
    let socket = null;
    let currentUserRole = window.CURRENT_USER_ROLE || 'guest';
    let currentUserId = window.CURRENT_USER_ID || 0;

    // -------------------------------------------------------------------------
    // 1. Toast Notification System
    // -------------------------------------------------------------------------
    function ensureToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    window.showCampusToast = function (title, message, type = 'info', duration = 5000) {
        const container = ensureToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        let icon = '📢';
        if (type === 'success') icon = '✓';
        else if (type === 'warning') icon = '⚠️';
        else if (type === 'error' || type === 'critical') icon = '🚨';
        else if (type === 'info') icon = 'ℹ️';

        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">
                <div class="toast-title">${escapeHtml(title)}</div>
                <div class="toast-message">${escapeHtml(message)}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
        `;

        container.appendChild(toast);

        // Auto remove unless critical SOS
        if (type !== 'critical') {
            setTimeout(() => {
                toast.classList.add('toast-leaving');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    };

    // -------------------------------------------------------------------------
    // 2. Notification Bell & Badge Updater
    // -------------------------------------------------------------------------
    function updateBellBadge(unreadCount) {
        const badges = document.querySelectorAll('.notif-badge-pill, #notif-badge-count');
        badges.forEach(b => {
            if (unreadCount > 0) {
                b.textContent = unreadCount > 99 ? '99+' : unreadCount;
                b.classList.add('visible');
                b.style.display = 'inline-block';
            } else {
                b.textContent = '0';
                b.classList.remove('visible');
                b.style.display = 'none';
            }
        });
    }

    async function fetchUnreadCount() {
        if (currentUserRole === 'guest') return;
        try {
            const resp = await fetch('/api/notifications/unread-count');
            if (resp.ok) {
                const data = await resp.json();
                updateBellBadge(data.unread_count);
            }
        } catch (e) {
            // Silently swallow fetch errors during network dips
        }
    }

    async function fetchRecentNotifications() {
        const listEl = document.getElementById('notif-dropdown-items');
        if (!listEl) return;

        try {
            listEl.innerHTML = '<div class="notif-empty-state">Loading notifications...</div>';
            const resp = await fetch('/api/notifications/recent');
            if (resp.ok) {
                const data = await resp.json();
                if (!data.notifications || data.notifications.length === 0) {
                    listEl.innerHTML = '<div class="notif-empty-state">No new notifications</div>';
                    return;
                }

                listEl.innerHTML = data.notifications.map(n => {
                    let catIcon = '📢';
                    if (n.category === 'Emergency' || n.priority === 'Critical') catIcon = '🚨';
                    else if (n.category === 'Attendance') catIcon = '📊';
                    else if (n.category === 'Academic') catIcon = '📚';
                    else if (n.category === 'Fees') catIcon = '💳';
                    else if (n.category === 'Timetable') catIcon = '📅';
                    else if (n.category === 'Leave') catIcon = '🏢';
                    else if (n.category === 'Message') catIcon = '💬';

                    let actionLinkHtml = n.action_url ? `<a href="${n.action_url}" style="color: #38bdf8; font-size: 0.76rem; font-weight: 700; margin-left: 8px;">Action →</a>` : '';

                    return `
                        <div class="notif-item ${n.is_read ? '' : 'unread'}" onclick="markNotificationRead(${n.id}, this)">
                            <div class="notif-item-icon">${catIcon}</div>
                            <div class="notif-item-body">
                                <div class="notif-item-title">
                                    <span>${escapeHtml(n.title)}</span>
                                </div>
                                <div class="notif-item-desc">${escapeHtml(n.message)}</div>
                                <div class="notif-item-time">${escapeHtml(n.created_at || '')} ${actionLinkHtml}</div>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        } catch (e) {
            listEl.innerHTML = '<div class="notif-empty-state">Unable to load alerts</div>';
        }
    }

    window.markNotificationRead = async function (id, el) {
        try {
            await fetch(`/api/notifications/mark-read/${id}`, { method: 'POST' });
            if (el) el.classList.remove('unread');
            fetchUnreadCount();
        } catch (e) { }
    };

    window.markAllNotificationsRead = async function () {
        try {
            await fetch('/api/notifications/mark-all-read', { method: 'POST' });
            const items = document.querySelectorAll('.notif-item.unread');
            items.forEach(i => i.classList.remove('unread'));
            updateBellBadge(0);
            window.showCampusToast('Updated', 'All notifications marked as read.', 'success');
        } catch (e) { }
    };

    function escapeHtml(text) {
        if (!text) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }

    // -------------------------------------------------------------------------
    // 3. Socket.IO Real-Time Dispatcher
    // -------------------------------------------------------------------------
    function initRealtimeSocket() {
        if (typeof io === 'undefined') {
            console.log('[CampusGuard] Socket.IO client library not loaded, using polling fallback.');
            startPolling();
            return;
        }

        try {
            socket = io({
                reconnection: true,
                reconnectionAttempts: 10,
                reconnectionDelay: 2000
            });

            socket.on('connect', () => {
                console.log('[CampusGuard Real-Time] Connected to WebSocket hub.');
                setConnectionStatus(true);
                
                // Join personal and role rooms
                if (currentUserId && currentUserRole !== 'guest') {
                    socket.emit('join_user_room', {
                        role: currentUserRole,
                        id: currentUserId
                    });
                }
            });

            socket.on('disconnect', () => {
                console.warn('[CampusGuard Real-Time] Disconnected from WebSocket hub.');
                setConnectionStatus(false);
            });

            // 1. Live Notification Broadcast
            socket.on('new_notification', (data) => {
                fetchUnreadCount();
                const type = data.priority === 'Critical' ? 'critical' : (data.priority === 'High' ? 'warning' : 'info');
                window.showCampusToast(data.title, data.message, type);
            });

            // 2. Live SOS Trigger Alert
            socket.on('sos_alert_triggered', (data) => {
                fetchUnreadCount();
                window.showCampusToast('🚨 CRITICAL SOS ALERT', `${data.student_name} broadcasted an emergency distress beacon at ${data.location}`, 'critical');
                // Refresh dashboard widgets if present
                if (typeof window.onCampusEmergencyUpdate === 'function') {
                    window.onCampusEmergencyUpdate(data);
                }
            });

            // 3. SOS Status Changed (Active -> Acknowledged -> Responding -> Resolved)
            socket.on('sos_status_changed', (data) => {
                fetchUnreadCount();
                window.showCampusToast('🛡️ Emergency Status Update', `Incident #${data.incident_id} is now ${data.status}`, 'info');
                if (typeof window.onCampusEmergencyUpdate === 'function') {
                    window.onCampusEmergencyUpdate(data);
                }
            });

            // 4. Attendance Updated
            socket.on('attendance_updated', (data) => {
                fetchUnreadCount();
                if (data.is_warning) {
                    window.showCampusToast('📊 Attendance Warning', `Attendance in ${data.subject_name} is now ${data.attendance_pct}% (below threshold)`, 'warning');
                } else {
                    window.showCampusToast('📊 Attendance Logged', `Attendance updated for ${data.subject_name}`, 'info');
                }
            });

            // 5. Marks Published
            socket.on('marks_published', (data) => {
                fetchUnreadCount();
                window.showCampusToast('📚 Marks Published', `New marks published for ${data.course_name} (${data.course_code})`, 'info');
            });

            // 6. Announcement Published
            socket.on('announcement_published', (data) => {
                fetchUnreadCount();
                window.showCampusToast(`📢 ${data.title}`, data.description, 'info');
            });

        } catch (e) {
            console.error('[CampusGuard] Socket init error:', e);
            startPolling();
        }
    }

    function setConnectionStatus(online) {
        const pills = document.querySelectorAll('.conn-status-pill');
        pills.forEach(p => {
            if (online) {
                p.classList.remove('offline');
                p.innerHTML = '<span class="conn-dot"></span> <span>Live Connected</span>';
            } else {
                p.classList.add('offline');
                p.innerHTML = '<span class="conn-dot"></span> <span>Reconnecting...</span>';
            }
        });
    }

    function startPolling() {
        fetchUnreadCount();
        setInterval(fetchUnreadCount, 12000);
    }

    // -------------------------------------------------------------------------
    // 4. Initialization on DOM Loaded
    // -------------------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', () => {
        // Wire up bell toggle
        const bellBtn = document.getElementById('notif-bell-btn');
        const menu = document.getElementById('notif-dropdown-menu');

        if (bellBtn && menu) {
            bellBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                menu.classList.toggle('open');
                if (menu.classList.contains('open')) {
                    fetchRecentNotifications();
                }
            });

            document.addEventListener('click', (e) => {
                if (!menu.contains(e.target) && !bellBtn.contains(e.target)) {
                    menu.classList.remove('open');
                }
            });
        }

        // Initialize real-time WebSocket connection
        initRealtimeSocket();
        fetchUnreadCount();
    });

})();
