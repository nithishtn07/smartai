/**
 * CampusGuard AI - Enterprise Student Portal Client Script
 * Handles mobile sidebar, modals, AI Resume analysis simulation,
 * simulated fee checkout, safe route rendering, and AI Chat client.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Sidebar Drawer Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('student-sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    if (mobileMenuBtn && sidebar && sidebarOverlay) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('is-open');
            sidebarOverlay.classList.toggle('is-open');
        });

        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('is-open');
            sidebarOverlay.classList.remove('is-open');
        });
    }

    // 2. Generic Modal Open/Close Controls
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.add('is-open');
    };

    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.remove('is-open');
    };

    // Close on backdrop click
    document.querySelectorAll('.portal-modal-backdrop').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('is-open');
            }
        });
    });

    // 3. Tab Switching Component
    const tabBtns = document.querySelectorAll('.tab-btn[data-tab]');
    const tabContents = document.querySelectorAll('.tab-content');

    if (tabBtns.length > 0) {
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                tabBtns.forEach(b => b.classList.remove('active'));
                tabContents.forEach(tc => tc.style.display = 'none');

                btn.classList.add('active');
                const targetContent = document.getElementById(`tab-${targetTab}`);
                if (targetContent) {
                    targetContent.style.display = 'block';
                }
            });
        });
    }

    // 4. Geolocation Attachment for Emergency SOS
    const sosForm = document.getElementById('sos-activation-form');
    const latInput = document.getElementById('sos-lat');
    const lngInput = document.getElementById('sos-lng');
    const locStatus = document.getElementById('sos-loc-status');

    if (sosForm && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                if (latInput && lngInput) {
                    latInput.value = pos.coords.latitude.toFixed(6);
                    lngInput.value = pos.coords.longitude.toFixed(6);
                }
                if (locStatus) {
                    locStatus.textContent = '📍 GPS Coordinates Locked';
                    locStatus.style.color = '#34d399';
                }
            },
            () => {
                if (locStatus) {
                    locStatus.textContent = '📍 Standard Campus Perimeter (GPS optional)';
                }
            },
            { timeout: 8000, enableHighAccuracy: true }
        );
    }

    // 5. Interactive AI Chat Assistant Client
    const chatForm = document.getElementById('assistant-chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const promptChips = document.querySelectorAll('.prompt-chip');

    function appendMessage(sender, text) {
        if (!chatMessages) return;
        const bubble = document.createElement('div');
        bubble.className = sender === 'user' ? 'chat-bubble chat-bubble-user' : 'chat-bubble chat-bubble-ai';
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    if (chatForm && chatInput && chatMessages) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (!message) return;

            appendMessage('user', message);
            chatInput.value = '';

            const typingBubble = document.createElement('div');
            typingBubble.className = 'chat-bubble chat-bubble-ai';
            typingBubble.id = 'ai-typing-indicator';
            typingBubble.innerHTML = '<em>CampusGuard AI is reasoning...</em>';
            chatMessages.appendChild(typingBubble);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            try {
                const response = await fetch('/api/student/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });

                const data = await response.json();
                typingBubble.remove();

                if (data.reply) {
                    appendMessage('ai', data.reply);
                } else {
                    appendMessage('ai', 'I apologize, but I could not retrieve that information right now.');
                }
            } catch (err) {
                if (typingBubble) typingBubble.remove();
                appendMessage('ai', 'CampusGuard AI assistant is in fallback offline mode.');
            }
        });

        promptChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const query = chip.getAttribute('data-prompt');
                if (query && chatInput) {
                    chatInput.value = query;
                    chatForm.dispatchEvent(new Event('submit'));
                }
            });
        });
    }

    // 6. AI Resume Analyzer Simulation
    const resumeForm = document.getElementById('resume-analysis-form');
    const resumeResultArea = document.getElementById('resume-result-area');

    if (resumeForm && resumeResultArea) {
        resumeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const skillsText = document.getElementById('resume-skills-input').value;
            const targetRole = document.getElementById('resume-target-role').value;

            resumeResultArea.innerHTML = '<div style="text-align: center; padding: 24px;"><div class="status-pulse" style="margin: 0 auto 12px; width: 14px; height: 14px;"></div><p style="color: #38bdf8;">AI Neural Engine parsing ATS keywords &amp; skill graph...</p></div>';

            try {
                const response = await fetch('/api/student/ai-resume', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ skills: skillsText, role: targetRole })
                });
                const data = await response.json();

                resumeResultArea.innerHTML = `
                    <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 14px; padding: 20px; margin-top: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <h4 style="color: #38bdf8; font-size: 1.1rem;">AI Match Score: <strong>${data.score}/100</strong></h4>
                            <span class="badge ${data.score >= 80 ? 'badge-green' : 'badge-yellow'}">${data.grade}</span>
                        </div>
                        <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin-bottom: 14px;">${data.feedback}</p>
                        <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 8px;">Recommended High-Impact Skills:</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px;">
                            ${data.recommended_skills.map(s => `<span class="badge badge-purple">+ ${s}</span>`).join('')}
                        </div>
                        <div style="font-size: 0.82rem; color: #34d399;">💡 <strong>Pro Tip:</strong> ${data.action_item}</div>
                    </div>
                `;
            } catch (err) {
                resumeResultArea.innerHTML = '<p style="color: #f87171;">Unable to run AI Resume analysis. Please try again.</p>';
            }
        });
    }

    // 7. Safe Route Calculator Interactive Handler
    const routeForm = document.getElementById('safe-route-form');
    const routeResultBox = document.getElementById('safe-route-result');

    if (routeForm && routeResultBox) {
        routeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fromLoc = document.getElementById('route-from').value;
            const toLoc = document.getElementById('route-to').value;

            routeResultBox.innerHTML = '<p style="color: #38bdf8;">Calculating optimal CCTV-monitored campus route...</p>';

            try {
                const res = await fetch('/api/student/safe-route', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ from: fromLoc, to: toLoc })
                });
                const data = await res.json();

                routeResultBox.innerHTML = `
                    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 16px; margin-top: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <strong style="color: #34d399; font-size: 0.95rem;">🛡️ Safe Route Verified</strong>
                            <span class="badge badge-green">98% Well-Lit Corridor</span>
                        </div>
                        <p style="color: var(--text-secondary); font-size: 0.86rem; margin-bottom: 10px;">${data.path_description}</p>
                        <div style="font-size: 0.8rem; color: var(--text-muted); display: flex; gap: 14px;">
                            <span>⏱️ Estimated Walk: <strong>${data.walk_time}</strong></span>
                            <span>📹 Active CCTV Coverage: <strong>${data.cctv_count} cameras</strong></span>
                            <span>🚨 Help Points Enroute: <strong>${data.help_points}</strong></span>
                        </div>
                    </div>
                `;
            } catch (err) {
                routeResultBox.innerHTML = '<p style="color: #f87171;">Safe route computation unavailable.</p>';
            }
        });
    }
});
