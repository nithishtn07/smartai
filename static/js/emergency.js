/**
 * CampusGuard AI — Emergency Response Client-Side Controller
 * Real-Time Socket.IO Synchronization, Geolocation Telemetry, Web Audio Chime, & Confirmation Modals.
 */

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // 1. Web Audio API Alarm Synthesizer (Zero External Dependencies)
    // -----------------------------------------------------------------------
    let audioCtx = null;
    let isSoundMuted = localStorage.getItem('campusguard_sound_muted') === 'true';

    function initAudioContext() {
        if (!audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                audioCtx = new AudioContextClass();
            }
        }
    }

    window.playEmergencyAlertSound = function () {
        if (isSoundMuted) return;
        try {
            initAudioContext();
            if (!audioCtx) return;

            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }

            const now = audioCtx.currentTime;
            
            // Tone 1: High alert frequency (880 Hz - A5)
            const osc1 = audioCtx.createOscillator();
            const gain1 = audioCtx.createGain();
            osc1.type = 'sawtooth';
            osc1.frequency.setValueAtTime(880, now);
            osc1.frequency.exponentialRampToValueAtTime(440, now + 0.35);

            gain1.gain.setValueAtTime(0.3, now);
            gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.35);

            osc1.connect(gain1);
            gain1.connect(audioCtx.destination);
            osc1.start(now);
            osc1.stop(now + 0.35);

            // Tone 2: Echo alert pulse (1046 Hz - C6)
            const osc2 = audioCtx.createOscillator();
            const gain2 = audioCtx.createGain();
            osc2.type = 'sine';
            osc2.frequency.setValueAtTime(1046, now + 0.18);
            osc2.frequency.exponentialRampToValueAtTime(523, now + 0.55);

            gain2.gain.setValueAtTime(0.25, now + 0.18);
            gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.55);

            osc2.connect(gain2);
            gain2.connect(audioCtx.destination);
            osc2.start(now + 0.18);
            osc2.stop(now + 0.55);

        } catch (e) {
            console.warn("[CampusGuard Audio] Chime playback skipped:", e);
        }
    };

    window.toggleEmergencyAudio = function (btnElement) {
        initAudioContext();
        isSoundMuted = !isSoundMuted;
        localStorage.setItem('campusguard_sound_muted', isSoundMuted ? 'true' : 'false');
        
        if (btnElement) {
            if (isSoundMuted) {
                btnElement.classList.remove('active');
                btnElement.innerHTML = `<span>🔇</span> Alarm Sound Muted`;
            } else {
                btnElement.classList.add('active');
                btnElement.innerHTML = `<span>🔊</span> Alarm Audio Enabled`;
                window.playEmergencyAlertSound();
            }
        }
    };


    // -----------------------------------------------------------------------
    // 2. Browser Geolocation API with Honest Fallback
    // -----------------------------------------------------------------------
    let liveGPSLocation = { latitude: null, longitude: null, accuracy: null, isAcquired: false };

    window.captureDeviceLocation = function (callbacks) {
        callbacks = callbacks || {};
        const onLocationCaptured = callbacks.onSuccess || function () {};
        const onLocationFailed = callbacks.onError || function () {};

        if (!navigator.geolocation) {
            liveGPSLocation.isAcquired = false;
            onLocationFailed("Browser Geolocation is not supported on this device.");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (position) {
                liveGPSLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    isAcquired: true
                };
                onLocationCaptured(liveGPSLocation);
            },
            function (error) {
                liveGPSLocation.isAcquired = false;
                let msg = "Location permission denied.";
                if (error.code === error.POSITION_UNAVAILABLE) msg = "Location information is unavailable.";
                if (error.code === error.TIMEOUT) msg = "Location request timed out.";
                onLocationFailed(msg);
            },
            {
                enableHighAccuracy: true,
                timeout: 8000,
                maximumAge: 10000
            }
        );
    };


    // -----------------------------------------------------------------------
    // 3. Topbar Quick SOS Click Handler & Modal Management
    // -----------------------------------------------------------------------
    let activeModalClockInterval = null;
    let selectedCategory = 'Personal Safety';

    window.handleTopbarSOSClick = async function (e) {
        if (e) e.preventDefault();

        try {
            // Check if student already has an active emergency
            const resp = await fetch('/api/emergency/my-active');
            if (resp.ok) {
                const data = await resp.json();
                if (data.status === 'active' && data.dossier && data.dossier.emergency) {
                    if (window.showCampusToast) {
                        window.showCampusToast('🚨 Emergency Response Active', `An emergency incident (${data.dossier.emergency.emergency_id}) is already active.`, 'warning');
                    }
                    if (window.location.pathname !== '/student/emergency') {
                        window.location.href = '/student/emergency';
                    } else {
                        const card = document.getElementById('active-emergency-tracker-card');
                        if (card) card.scrollIntoView({ behavior: 'smooth' });
                    }
                    return;
                }
            }
        } catch (err) {
            console.warn("[CampusGuard] Failed to check active emergency:", err);
        }

        // If no active emergency, open the Confirmation Modal
        window.openEmergencySOSModal();
    };

    window.openEmergencySOSModal = function () {
        const modal = document.getElementById('sos-confirm-modal');
        if (!modal) {
            // If modal not on current page, redirect to emergency page
            window.location.href = '/student/emergency?trigger=true';
            return;
        }

        // Update live time clock
        function updateModalClock() {
            const timeEl = document.getElementById('sos-modal-current-time');
            if (timeEl) {
                const now = new Date();
                timeEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            }
        }
        updateModalClock();
        if (activeModalClockInterval) clearInterval(activeModalClockInterval);
        activeModalClockInterval = setInterval(updateModalClock, 1000);

        // Reset category and inputs
        selectedCategory = 'Personal Safety';
        const pills = document.querySelectorAll('#sos-category-pills .category-pill');
        pills.forEach(p => {
            if (p.getAttribute('data-category') === 'Personal Safety') p.classList.add('active');
            else p.classList.remove('active');
        });

        const descInput = document.getElementById('sos-modal-description');
        if (descInput) descInput.value = '';

        // Reset loading state
        const loadingBox = document.getElementById('sos-activation-loading');
        const footerBtns = document.querySelector('.emergency-modal-footer');
        if (loadingBox) loadingBox.style.display = 'none';
        if (footerBtns) footerBtns.style.display = 'flex';

        // Trigger Geolocation capture
        const gpsStatus = document.getElementById('sos-modal-gps-status');
        const manualWrap = document.getElementById('sos-modal-manual-zone-wrap');
        if (gpsStatus) {
            gpsStatus.innerHTML = `<span>📍 Acquiring Device GPS Coordinates...</span>`;
            gpsStatus.style.color = '#38bdf8';
        }

        window.captureDeviceLocation({
            onSuccess: function (loc) {
                if (gpsStatus) {
                    gpsStatus.innerHTML = `<span>📍 GPS Acquired (${loc.latitude.toFixed(4)}, ${loc.longitude.toFixed(4)} ±${Math.round(loc.accuracy)}m)</span>`;
                    gpsStatus.style.color = '#34d399';
                }
                if (manualWrap) manualWrap.style.display = 'none';
            },
            onError: function (msg) {
                if (gpsStatus) {
                    gpsStatus.innerHTML = `<span>⚠️ Location unavailable. Emergency team notified without GPS telemetry.</span>`;
                    gpsStatus.style.color = '#f59e0b';
                }
                if (manualWrap) manualWrap.style.display = 'block';
            }
        });

        // Update AI assessment preview
        updateAIAssessmentPreview(selectedCategory, '');

        modal.style.display = 'flex';
    };

    window.closeEmergencySOSModal = function () {
        const modal = document.getElementById('sos-confirm-modal');
        if (modal) modal.style.display = 'none';
        if (activeModalClockInterval) clearInterval(activeModalClockInterval);
    };

    window.selectSOSCategory = function (categoryName, btnEl) {
        selectedCategory = categoryName;
        const pills = document.querySelectorAll('#sos-category-pills .category-pill');
        pills.forEach(p => p.classList.remove('active'));
        if (btnEl) btnEl.classList.add('active');

        const descInput = document.getElementById('sos-modal-description');
        updateAIAssessmentPreview(categoryName, descInput ? descInput.value : '');
    };

    window.onSOSDescriptionInput = function (text) {
        updateAIAssessmentPreview(selectedCategory, text);
    };

    function updateAIAssessmentPreview(category, description) {
        const previewText = document.getElementById('sos-ai-preview-text');
        if (!previewText) return;

        let priority = 'HIGH';
        let badgeColor = 'rgba(249, 115, 22, 0.2)';
        let textColor = '#fdba74';
        let borderColor = 'rgba(249, 115, 22, 0.4)';

        const textLower = (category + " " + description).toLowerCase();
        if (textLower.includes('medical') || textLower.includes('heart') || textLower.includes('collapse') ||
            textLower.includes('fire') || textLower.includes('smoke') || textLower.includes('weapon') || textLower.includes('assault')) {
            priority = 'CRITICAL';
            badgeColor = 'rgba(239, 68, 68, 0.2)';
            textColor = '#fca5a5';
            borderColor = 'rgba(239, 68, 68, 0.4)';
        }

        let summary = `Analyzing emergency signal... <strong>${category}</strong> classified.`;
        if (description.trim()) {
            summary = `Analyzing input: "<em>${description.trim().substring(0, 45)}...</em>" — Fast Dispatch Recommended.`;
        }

        previewText.innerHTML = `
            ${summary} 
            <span class="badge" style="background: ${badgeColor}; color: ${textColor}; border: 1px solid ${borderColor}; margin-left: 6px;">
                Priority: ${priority}
            </span>
        `;
    }


    // -----------------------------------------------------------------------
    // 4. Submit Emergency SOS Activation Flow
    // -----------------------------------------------------------------------
    window.submitEmergencySOSActivation = async function () {
        const activateBtn = document.getElementById('btn-activate-sos');
        const cancelBtn = document.getElementById('btn-cancel-sos');
        const loadingBox = document.getElementById('sos-activation-loading');
        const stepText = document.getElementById('sos-loading-step-text');
        const descInput = document.getElementById('sos-modal-description');
        const manualZoneSelect = document.getElementById('sos-modal-manual-zone');

        if (activateBtn) activateBtn.disabled = true;
        if (cancelBtn) cancelBtn.disabled = true;
        if (loadingBox) loadingBox.style.display = 'block';

        // Step 1: Activating
        if (stepText) stepText.textContent = "Activating Emergency SOS...";
        await new Promise(r => setTimeout(r, 250));

        // Step 2: Telemetry Gathering
        if (stepText) stepText.textContent = "Locating device coordinates...";
        await new Promise(r => setTimeout(r, 200));

        const description = descInput ? descInput.value.trim() : '';
        const campusZone = (manualZoneSelect && manualZoneSelect.value) ? manualZoneSelect.value : 'Main Academic Block';

        // Step 3: Dispatching to Backend
        if (stepText) stepText.textContent = "Notifying emergency response team...";

        const payload = {
            category: selectedCategory,
            description: description,
            campus_zone: campusZone,
            latitude: liveGPSLocation.isAcquired ? liveGPSLocation.latitude : null,
            longitude: liveGPSLocation.isAcquired ? liveGPSLocation.longitude : null,
            accuracy: liveGPSLocation.isAcquired ? liveGPSLocation.accuracy : null,
            severity: selectedCategory === 'Medical Emergency' || selectedCategory === 'Fire/Safety' ? 'CRITICAL' : 'HIGH'
        };

        try {
            const resp = await fetch('/api/emergency/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();

            if (data.status === 'success' || data.status === 'already_active') {
                if (stepText) stepText.textContent = "Emergency team notified! Connecting...";
                window.playEmergencyAlertSound();

                if (window.showCampusToast) {
                    window.showCampusToast(
                        '🚨 SOS Activated',
                        'Your emergency request has been sent to the campus response team.',
                        'critical'
                    );
                }

                await new Promise(r => setTimeout(r, 350));
                window.closeEmergencySOSModal();

                if (window.location.pathname === '/student/emergency') {
                    window.location.reload();
                } else {
                    window.location.href = '/student/emergency';
                }
            } else {
                alert("Emergency activation error: " + (data.message || 'Please try again or call emergency helpline.'));
                if (activateBtn) activateBtn.disabled = false;
                if (cancelBtn) cancelBtn.disabled = false;
                if (loadingBox) loadingBox.style.display = 'none';
            }
        } catch (err) {
            console.error("[CampusGuard SOS] Activation network error:", err);
            alert("Network connectivity issue. Please call the Campus Security Control Room at +91 91234 56780 immediately.");
            if (activateBtn) activateBtn.disabled = false;
            if (cancelBtn) cancelBtn.disabled = false;
            if (loadingBox) loadingBox.style.display = 'none';
        }
    };


    // -----------------------------------------------------------------------
    // 5. Stand Down (Mark Safe) Flow
    // -----------------------------------------------------------------------
    let pendingStandDownId = null;

    window.openStandDownModal = function (emergencyId) {
        pendingStandDownId = emergencyId;
        const modal = document.getElementById('sos-stand-down-modal');
        if (modal) modal.style.display = 'flex';
    };

    window.closeStandDownModal = function () {
        const modal = document.getElementById('sos-stand-down-modal');
        if (modal) modal.style.display = 'none';
        pendingStandDownId = null;
    };

    window.confirmStandDown = async function () {
        if (!pendingStandDownId) return;
        const emgId = pendingStandDownId;
        window.closeStandDownModal();

        try {
            const resp = await fetch(`/student/emergency/cancel/${emgId}`, {
                method: 'POST'
            });

            if (window.showCampusToast) {
                window.showCampusToast('🛡️ Marked Safe', 'Your stand-down notice has been dispatched to the response team.', 'success');
            }
            setTimeout(() => {
                window.location.reload();
            }, 500);
        } catch (e) {
            alert("Error standing down emergency. Please refresh and try again.");
        }
    };


    // -----------------------------------------------------------------------
    // 6. Real-Time Student Emergency Listener & Dynamic DOM Synchronizer
    // -----------------------------------------------------------------------
    window.initStudentEmergencyListener = function (initialEmergencyId) {
        let lastStatus = null;
        let lastAssignedUnit = null;

        async function pollMyActiveEmergency() {
            try {
                const resp = await fetch('/api/emergency/my-active');
                if (!resp.ok) return;
                const data = await resp.json();

                if (data.status === 'active' && data.dossier && data.dossier.emergency) {
                    const emg = data.dossier.emergency;
                    syncActiveEmergencyUI(emg);
                } else if (data.status === 'none' && lastStatus && lastStatus !== 'RESOLVED' && lastStatus !== 'CLOSED' && lastStatus !== 'CANCELLED') {
                    // Stood down or resolved externally
                    window.location.reload();
                }
            } catch (err) {
                console.warn("[CampusGuard] Emergency sync polling dip:", err);
            }
        }

        function syncActiveEmergencyUI(emg) {
            const status = emg.status;
            const assignedUnit = emg.assigned_responder || 'Awaiting assignment';

            // Check if status changed
            if (lastStatus && lastStatus !== status) {
                handleStatusTransitionToast(lastStatus, status, emg);
            }

            // Check if assigned unit changed
            if (lastAssignedUnit && lastAssignedUnit !== assignedUnit && assignedUnit !== 'Awaiting assignment') {
                if (window.showCampusToast) {
                    window.showCampusToast('⚡ Response Unit Assigned', `${assignedUnit} has been assigned to your emergency.`, 'warning');
                }
            }

            lastStatus = status;
            lastAssignedUnit = assignedUnit;

            // Update DOM Elements
            const statusPill = document.getElementById('live-status-pill');
            if (statusPill) {
                updateStatusPill(statusPill, status);
            }

            const assignedUnitText = document.getElementById('live-assigned-unit');
            if (assignedUnitText) {
                assignedUnitText.textContent = assignedUnit;
            }

            // Update 6-Stage Timeline Steps
            updateTimelineSteps(emg);
        }

        function updateStatusPill(el, status) {
            el.className = 'live-status-pill';
            if (status === 'TRIGGERED') {
                el.classList.add('status-triggered');
                el.innerHTML = `<span class="beacon-dot"></span> 🟢 Response Team Notified`;
            } else if (status === 'ACKNOWLEDGED') {
                el.classList.add('status-acknowledged');
                el.innerHTML = `<span>✓</span> 🔵 Incident Acknowledged`;
            } else if (status === 'RESPONDER_ASSIGNED' || status === 'ASSIGNED') {
                el.classList.add('status-assigned');
                el.innerHTML = `<span>⚡</span> 🟡 Response Unit Assigned`;
            } else if (status === 'EN_ROUTE') {
                el.classList.add('status-enroute');
                el.innerHTML = `<span>🚗</span> 🚑 Responder En Route`;
            } else if (status === 'ON_SCENE') {
                el.classList.add('status-onscene');
                el.innerHTML = `<span>📍</span> 📍 Responder On Scene`;
            } else if (status === 'RESOLVED' || status === 'CLOSED') {
                el.classList.add('status-resolved');
                el.innerHTML = `<span>🛡️</span> 🛡️ Emergency Resolved`;
            }
        }

        function updateTimelineSteps(emg) {
            const status = emg.status;
            const step1 = document.getElementById('step-triggered');
            const step2 = document.getElementById('step-acknowledged');
            const step3 = document.getElementById('step-assigned');
            const step4 = document.getElementById('step-enroute');
            const step5 = document.getElementById('step-onscene');
            const step6 = document.getElementById('step-resolved');

            const isAck = ['ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'RESOLVED', 'CLOSED'].includes(status);
            const isAssigned = ['ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'RESOLVED', 'CLOSED'].includes(status);
            const isEnRoute = ['EN_ROUTE', 'ON_SCENE', 'RESOLVED', 'CLOSED'].includes(status);
            const isOnScene = ['ON_SCENE', 'RESOLVED', 'CLOSED'].includes(status);
            const isResolved = ['RESOLVED', 'CLOSED'].includes(status);

            if (step1) {
                step1.className = 'timeline-step-card completed';
                const timeEl = step1.querySelector('.step-time');
                if (timeEl && emg.created_at) timeEl.textContent = emg.created_at.substring(11, 16);
            }

            if (step2) {
                step2.className = `timeline-step-card ${isAck ? 'completed' : 'active'}`;
                const timeEl = step2.querySelector('.step-time');
                if (timeEl) timeEl.textContent = isAck ? (emg.acknowledged_at ? emg.acknowledged_at.substring(11, 16) : 'Confirmed') : 'Waiting for response team';
            }

            if (step3) {
                step3.className = `timeline-step-card ${isAssigned ? 'completed' : (status === 'ACKNOWLEDGED' ? 'active' : 'pending')}`;
                const timeEl = step3.querySelector('.step-time');
                if (timeEl) timeEl.textContent = isAssigned ? (emg.assigned_responder || 'Assigned') : 'Waiting';
            }

            if (step4) {
                step4.className = `timeline-step-card ${isEnRoute ? 'completed' : (status === 'RESPONDER_ASSIGNED' || status === 'ASSIGNED' ? 'active' : 'pending')}`;
                const timeEl = step4.querySelector('.step-time');
                if (timeEl) timeEl.textContent = isEnRoute ? (emg.response_started_at ? emg.response_started_at.substring(11, 16) : 'En Route (ETA ~4m)') : 'Waiting';
            }

            if (step5) {
                step5.className = `timeline-step-card ${isOnScene ? 'completed' : (status === 'EN_ROUTE' ? 'active' : 'pending')}`;
                const timeEl = step5.querySelector('.step-time');
                if (timeEl) timeEl.textContent = isOnScene ? (emg.arrived_at ? emg.arrived_at.substring(11, 16) : 'On Scene') : 'Waiting';
            }

            if (step6) {
                step6.className = `timeline-step-card ${isResolved ? 'completed' : (status === 'ON_SCENE' ? 'active' : 'pending')}`;
                const timeEl = step6.querySelector('.step-time');
                if (timeEl) timeEl.textContent = isResolved ? (emg.resolved_at ? emg.resolved_at.substring(11, 16) : 'Resolved') : 'Pending';
            }
        }

        function handleStatusTransitionToast(oldStatus, newStatus, emg) {
            window.playEmergencyAlertSound();
            if (!window.showCampusToast) return;

            if (newStatus === 'ACKNOWLEDGED') {
                window.showCampusToast('🛡️ Incident Acknowledged', 'The emergency response team has received your SOS.', 'info');
            } else if (newStatus === 'RESPONDER_ASSIGNED' || newStatus === 'ASSIGNED') {
                window.showCampusToast('⚡ Response Unit Assigned', `${emg.assigned_responder || 'Campus Security'} has been assigned.`, 'warning');
            } else if (newStatus === 'EN_ROUTE') {
                window.showCampusToast('🚑 Responder En Route', 'Your assigned response team is travelling to your location. Estimated arrival: 4 minutes', 'warning');
            } else if (newStatus === 'ON_SCENE') {
                window.showCampusToast('📍 Responder On Scene', 'A campus emergency responder has arrived at your reported location.', 'success');
            } else if (newStatus === 'RESOLVED' || newStatus === 'CLOSED') {
                window.showCampusToast('✓ Emergency Resolved', 'Your emergency incident has been marked as resolved.', 'success');
            }
        }

        // Poll every 3 seconds
        setInterval(pollMyActiveEmergency, 3000);
        pollMyActiveEmergency();
    };


    // -----------------------------------------------------------------------
    // 7. Command Center Live Stream & Active Queue Auto-Refresh (Admin/Security)
    // -----------------------------------------------------------------------
    window.initCommandCenterLiveStream = function () {
        let lastKnownCount = null;

        async function pollActiveEmergencies() {
            try {
                const resp = await fetch('/api/emergency/active');
                if (!resp.ok) return;
                const data = await resp.json();

                if (data.status === 'success') {
                    if (lastKnownCount !== null && data.count > lastKnownCount) {
                        window.playEmergencyAlertSound();
                    }
                    lastKnownCount = data.count;
                    const countBadge = document.getElementById('active-emergency-count');
                    if (countBadge) {
                        countBadge.textContent = `${emergencies.length} Active Alert${emergencies.length === 1 ? '' : 's'}`;
                    }
                }
            } catch (err) {
                console.warn("[CampusGuard Live] Polling error:", err);
            }
        }

        setInterval(pollActiveEmergencies, 4000);
        pollActiveEmergencies();
    };

    // -----------------------------------------------------------------------
    // 8. Auto-Initialization on Page Load
    // -----------------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', () => {
        // Auto-check URL parameters for ?trigger=true
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('trigger') === 'true') {
            setTimeout(() => {
                window.openEmergencySOSModal();
            }, 300);
        }
    });

})();
