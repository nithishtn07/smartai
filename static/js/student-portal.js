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
    const clearChatBtn = document.getElementById('clear-chat-btn');
    let sessionContext = {};

    function escapeHtml(text) {
        if (!text) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }

    function formatAiResponse(text) {
        if (!text) return '';
        let formatted = escapeHtml(text);
        // Links: [Label](url)
        formatted = formatted.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_self" style="color: #38bdf8; font-weight: 700; text-decoration: underline;">$1</a>');
        // Bold: **text**
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Italic / emphasis: *text* or _text_
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
        formatted = formatted.replace(/_(.*?)_/g, '<em>$1</em>');
        // Inline code: `code`
        formatted = formatted.replace(/`([^`]+)`/g, '<code style="background: rgba(15, 23, 42, 0.7); padding: 2px 6px; border-radius: 4px; color: #38bdf8; font-family: monospace; font-size: 0.85em;">$1</code>');
        // Linebreaks
        formatted = formatted.replace(/\n/g, '<br>');
        return formatted;
    }

    function appendMessage(sender, text, intent = '', suggestions = [], userQuery = '') {
        if (!chatMessages) return;
        const bubble = document.createElement('div');
        const msgId = 'msg-' + Date.now();
        bubble.className = sender === 'user' ? 'chat-bubble chat-bubble-user' : 'chat-bubble chat-bubble-ai';
        bubble.id = msgId;

        if (intent === 'EMERGENCY_SAFETY') {
            bubble.style.border = '1px solid #ef4444';
            bubble.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(153, 27, 27, 0.3) 100%)';
            bubble.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.3)';
        }

        if (sender === 'user') {
            bubble.textContent = text;
        } else {
            let inner = formatAiResponse(text);
            
            // Render Feedback buttons
            inner += `
                <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);">
                    <span>Was this helpful?</span>
                    <div style="display: flex; gap: 8px;">
                        <button type="button" class="ai-feedback-btn" data-rating="up" data-query="${escapeHtml(userQuery)}" style="background: none; border: 1px solid var(--glass-border); border-radius: 6px; padding: 2px 8px; color: var(--text-secondary); cursor: pointer;" title="Helpful response">👍 Helpful</button>
                        <button type="button" class="ai-feedback-btn" data-rating="down" data-query="${escapeHtml(userQuery)}" style="background: none; border: 1px solid var(--glass-border); border-radius: 6px; padding: 2px 8px; color: var(--text-secondary); cursor: pointer;" title="Not helpful">👎 Not Helpful</button>
                    </div>
                </div>
            `;

            bubble.innerHTML = inner;

            // Render interactive contextual suggestion pills if available
            if (suggestions && suggestions.length > 0) {
                const suggContainer = document.createElement('div');
                suggContainer.style.display = 'flex';
                suggContainer.style.flexWrap = 'wrap';
                suggContainer.style.gap = '6px';
                suggContainer.style.marginTop = '8px';

                suggestions.forEach(s => {
                    const pill = document.createElement('span');
                    pill.className = 'prompt-chip';
                    pill.style.fontSize = '0.74rem';
                    pill.style.padding = '4px 10px';
                    pill.textContent = s;
                    pill.addEventListener('click', () => {
                        if (chatInput && chatForm) {
                            chatInput.value = s.replace(/^[^\w\s]+/, '').trim();
                            chatForm.dispatchEvent(new Event('submit'));
                        }
                    });
                    suggContainer.appendChild(pill);
                });
                bubble.appendChild(suggContainer);
            }
        }

        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Attach feedback event listeners
        bubble.querySelectorAll('.ai-feedback-btn').forEach(btn => {
            btn.addEventListener('click', async function() {
                const rating = this.getAttribute('data-rating');
                const query = this.getAttribute('data-query');
                const parent = this.parentElement;
                parent.innerHTML = rating === 'up' ? '<span style="color: #34d399;">✓ Thank you for your feedback!</span>' : '<span style="color: #fbbf24;">✓ Feedback noted.</span>';

                try {
                    await fetch('/api/student/ai-feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ rating: rating, query: query })
                    });
                } catch(e) {}
            });
        });
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
            typingBubble.innerHTML = '<em>CampusGuard AI is reasoning from verified records...</em>';
            chatMessages.appendChild(typingBubble);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            try {
                const response = await fetch('/api/student/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message, query: message, session_context: sessionContext })
                });

                const data = await response.json();
                typingBubble.remove();

                if (data.reply) {
                    if (data.intent) {
                        sessionContext.last_intent = data.intent;
                    }
                    appendMessage('ai', data.reply, data.intent || '', data.suggestions || [], message);
                } else {
                    appendMessage('ai', 'I apologize, but I could not retrieve that information right now.', '', [], message);
                }
            } catch (err) {
                if (typingBubble) typingBubble.remove();
                appendMessage('ai', 'CampusGuard AI assistant is in fallback offline mode. Your standard campus modules remain fully operational.', '', [], message);
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

        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', () => {
                sessionContext = {};
                chatMessages.innerHTML = `
                    <div class="chat-bubble chat-bubble-ai">
                        🔄 <em>Conversation history cleared.</em><br><br>
                        How can I assist you with your attendance, lectures, exams, marks, study plan, or safety?
                    </div>
                `;
            });
        }
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
