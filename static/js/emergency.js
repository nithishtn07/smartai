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
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            });

            if (window.showCampusToast) {
                window.showCampusToast('🛡️ Marked Safe', 'Your stand-down notice has been dispatched. You are marked SAFE.', 'success');
            }

            // Immediately switch UI to Safe & Ready state with active alert button
            showSafeReadyView(emgId);

            setTimeout(() => {
                window.location.reload();
            }, 600);
        } catch (e) {
            console.error("Error standing down emergency:", e);
            alert("Error standing down emergency. Please refresh and try again.");
        }
    };

    window.acknowledgeEmergency = async function (emergencyId) {
        try {
            const resp = await fetch(`/api/emergency/${emergencyId}/acknowledge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes: 'Incident acknowledged by Campus Security Command.' })
            });
            if (resp.ok) {
                window.location.reload();
            } else {
                const data = await resp.json();
                alert(data.message || "Failed to acknowledge emergency.");
            }
        } catch (e) {
            console.error("Error acknowledging emergency:", e);
        }
    };


    // -----------------------------------------------------------------------
    // 6. Real-Time Student Emergency Listener & Dynamic DOM Synchronizer
    // -----------------------------------------------------------------------
    const ACTIVE_STATUSES = ['TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'ACTIVE', 'RESPONDING'];
    const RESOLVED_STATUSES = ['RESOLVED', 'CLOSED'];
    const STAND_DOWN_STATUSES = ['STAND_DOWN', 'CANCELLED', 'SAFE'];

    window.initStudentEmergencyListener = function (initialEmergencyId) {
        let lastStatus = null;
        let lastAssignedUnit = null;

        async function fetchLatestEmergencyStatus() {
            try {
                const resp = await fetch('/api/student/emergency/status?t=' + Date.now(), {
                    cache: 'no-store'
                });
                if (!resp.ok) return;
                const data = await resp.json();

                if (data.success && data.has_emergency) {
                    syncStudentEmergencyDOM(data);
                } else {
                    showNeutralReadyView();
                }
            } catch (err) {
                console.warn("[CampusGuard] Emergency status sync polling err:", err);
            }
        }

        function syncStudentEmergencyDOM(emg) {
            const status = (emg.status || 'TRIGGERED').toUpperCase();
            const assignedUnit = emg.assigned_responder || emg.assigned_to || 'Quick Response Team';
            const incidentId = emg.incident_id || emg.emergency_id || '';

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

            const activeCard = document.getElementById('active-emergency-tracker-card');
            const resolvedCard = document.getElementById('resolved-emergency-card');
            const readyCard = document.getElementById('neutral-ready-card');

            if (ACTIVE_STATUSES.includes(status)) {
                if (activeCard) activeCard.style.display = 'block';
                if (resolvedCard) resolvedCard.style.display = 'none';
                if (readyCard) readyCard.style.display = 'none';

                // Update Header & ID
                const idSpan = document.getElementById('active-sos-id-span');
                if (idSpan) idSpan.textContent = incidentId;

                // Update Telemetry Elements
                const telId = document.getElementById('live-telemetry-id');
                if (telId) telId.textContent = incidentId;
                const telCat = document.getElementById('live-telemetry-category');
                if (telCat) telCat.textContent = emg.category || emg.emergency_type || 'Personal Safety';
                const telLoc = document.getElementById('live-telemetry-location');
                if (telLoc) telLoc.textContent = emg.location || emg.campus_zone || 'Campus Safe Zone';
                const telUnit = document.getElementById('live-assigned-unit');
                if (telUnit) telUnit.textContent = assignedUnit;
                const telTime = document.getElementById('live-telemetry-time');
                if (telTime && emg.created_at) telTime.textContent = emg.created_at.substring(0, 16);

                const dossierBtn = document.getElementById('active-sos-dossier-btn');
                if (dossierBtn && incidentId) dossierBtn.href = `/emergency/incident/${incidentId}`;

                // Update Status Pill
                const statusPill = document.getElementById('live-status-pill');
                if (statusPill) updateStatusPill(statusPill, status);

                // Update 6-Stage Timeline Steps
                updateTimelineSteps(emg);

            } else if (STAND_DOWN_STATUSES.includes(status)) {
                // False alarm stood down -> Show Ready card with Safe status and USABLE SOS button!
                showSafeReadyView(incidentId);

            } else if (RESOLVED_STATUSES.includes(status)) {
                if (activeCard) activeCard.style.display = 'none';
                if (resolvedCard) resolvedCard.style.display = 'block';
                if (readyCard) readyCard.style.display = 'none';

                // Update Resolved Card Elements
                const rId = document.getElementById('resolved-incident-id');
                if (rId) rId.textContent = incidentId;
                const rStatus = document.getElementById('resolved-status-text');
                if (rStatus) rStatus.textContent = status;
                const rCat = document.getElementById('resolved-category-text');
                if (rCat) rCat.textContent = emg.category || emg.emergency_type || 'Personal Safety';
                const rLoc = document.getElementById('resolved-location-text');
                if (rLoc) rLoc.textContent = emg.location || emg.campus_zone || 'Campus Safe Zone';
                const rTime = document.getElementById('resolved-time-text');
                if (rTime) rTime.textContent = emg.resolved_at || emg.closed_at || emg.updated_at || 'Confirmed';
                const rUnit = document.getElementById('resolved-unit-text');
                if (rUnit) rUnit.textContent = assignedUnit;
                const rLink = document.getElementById('resolved-dossier-link');
                if (rLink && incidentId) rLink.href = `/emergency/incident/${incidentId}`;

                const rSub = document.getElementById('resolved-card-subtitle');
                if (rSub) {
                    if (status === 'RESOLVED') {
                        rSub.textContent = "Your emergency has been safely handled. Situation confirmed secure by Campus Security Command.";
                    } else if (status === 'CLOSED') {
                        rSub.textContent = "Your emergency incident is formally closed and archived.";
                    }
                }
            } else {
                showNeutralReadyView();
            }
        }

        function showSafeReadyView(incidentId) {
            const activeCard = document.getElementById('active-emergency-tracker-card');
            const resolvedCard = document.getElementById('resolved-emergency-card');
            const readyCard = document.getElementById('neutral-ready-card');
            const safeBanner = document.getElementById('sos-safe-banner');

            if (activeCard) activeCard.style.display = 'none';
            if (resolvedCard) resolvedCard.style.display = 'none';
            if (readyCard) readyCard.style.display = 'block';

            if (safeBanner) {
                safeBanner.style.display = 'flex';
                if (incidentId) {
                    safeBanner.innerHTML = `
                        <span style="font-size: 1.6rem;">🛡️</span>
                        <div>
                            <div>Status: <strong style="color: white;">SAFE</strong> (False Alarm / Stand Down Confirmed)</div>
                            <div style="font-size: 0.82rem; color: #a7f3d0; font-weight: 400;">Distress beacon (${incidentId}) was stood down. Emergency response is cancelled. Distress beacon is on standby and ready.</div>
                        </div>
                    `;
                }
            }
        }

        function showNeutralReadyView() {
            const activeCard = document.getElementById('active-emergency-tracker-card');
            const resolvedCard = document.getElementById('resolved-emergency-card');
            const readyCard = document.getElementById('neutral-ready-card');

            if (activeCard) activeCard.style.display = 'none';
            if (resolvedCard) resolvedCard.style.display = 'none';
            if (readyCard) readyCard.style.display = 'block';
        }

        window.dismissResolvedEmergencyView = function () {
            showNeutralReadyView();
        };

        function updateStatusPill(el, status) {
            el.className = 'live-status-pill';
            if (status === 'TRIGGERED' || status === 'ACTIVE') {
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

        // Socket.IO Real-Time Connection Hook
        if (typeof io !== 'undefined') {
            try {
                const socket = io();
                socket.on('emergency_status_update', function (data) {
                    fetchLatestEmergencyStatus();
                });
            } catch (e) {
                console.warn("[CampusGuard Socket] emergency_status_update listener fallback to polling");
            }
        }

        // Browser navigation & return lifecycle events (pageshow, focus, visibilitychange)
        window.addEventListener('focus', fetchLatestEmergencyStatus);
        window.addEventListener('pageshow', fetchLatestEmergencyStatus);
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) fetchLatestEmergencyStatus();
        });

        // 2.5 second polling fallback
        setInterval(fetchLatestEmergencyStatus, 2500);
        fetchLatestEmergencyStatus();
    };


    // -----------------------------------------------------------------------
    // 7. Dynamic Dashboard Emergency Banner Listener (Student & Parent)
    // -----------------------------------------------------------------------
    window.initDashboardEmergencyBannerListener = function (role) {
        role = role || 'student';
        const endpoint = role === 'parent' ? '/api/parent/emergency/status' : '/api/student/emergency/status';

        async function syncDashboardBanner() {
            try {
                const resp = await fetch(endpoint + '?t=' + Date.now(), { cache: 'no-store' });
                if (!resp.ok) return;
                const data = await resp.json();

                const banner = document.getElementById(role + '-dashboard-sos-banner');
                if (!banner) return;

                if (data.success && data.has_emergency) {
                    const status = (data.status || 'TRIGGERED').toUpperCase();
                    if (ACTIVE_STATUSES.includes(status)) {
                        banner.style.display = 'flex';
                        banner.style.borderColor = '#ef4444';
                        banner.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.18) 0%, rgba(153, 27, 27, 0.25) 100%)';
                        const title = banner.querySelector('h3');
                        if (title) title.innerHTML = `EMERGENCY SOS ACTIVE: <span style="font-family: var(--font-mono);">${data.incident_id}</span> (${status})`;
                        const sub = banner.querySelector('p');
                        if (sub) sub.innerHTML = `Location: <strong>${data.location || 'Campus Safe Zone'}</strong>. Unit: <strong>${data.assigned_responder || 'Quick Response Team'}</strong> is responding.`;
                    } else if (COMPLETED_STATUSES.includes(status)) {
                        banner.style.display = 'flex';
                        banner.style.borderColor = 'rgba(52, 211, 153, 0.5)';
                        banner.style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.14) 0%, rgba(14, 19, 32, 0.96) 100%)';
                        const title = banner.querySelector('h3');
                        if (title) title.innerHTML = `✓ EMERGENCY RESOLVED: <span style="font-family: var(--font-mono);">${data.incident_id}</span>`;
                        const sub = banner.querySelector('p');
                        if (sub) sub.innerHTML = `Emergency safely resolved at <strong>${data.resolved_at || data.updated_at || 'Recently'}</strong>. Safety confirmed by Security Command.`;
                    } else {
                        banner.style.display = 'none';
                    }
                }
            } catch (err) {
                console.warn("[CampusGuard Dashboard Banner] Sync dip:", err);
            }
        }

        // Socket.IO hook
        if (typeof io !== 'undefined') {
            try {
                const socket = io();
                socket.on('emergency_status_update', function () {
                    syncDashboardBanner();
                });
            } catch (e) {}
        }

        window.addEventListener('focus', syncDashboardBanner);
        window.addEventListener('pageshow', syncDashboardBanner);
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) syncDashboardBanner();
        });

        setInterval(syncDashboardBanner, 3000);
        syncDashboardBanner();
    };


    // -----------------------------------------------------------------------
    // 8. Real-Time Parent Safety Center Synchronizer
    // -----------------------------------------------------------------------
    window.initParentSafetyListener = function () {
        async function syncParentSafety() {
            try {
                const resp = await fetch('/api/parent/emergency/status?t=' + Date.now(), { cache: 'no-store' });
                if (!resp.ok) return;
                const data = await resp.json();

                const activeCard = document.getElementById('parent-active-sos-card');
                const resolvedCard = document.getElementById('parent-resolved-sos-card');
                const normalCard = document.getElementById('parent-normal-safe-card');

                if (data.success && data.has_emergency) {
                    const status = (data.status || 'TRIGGERED').toUpperCase();
                    if (ACTIVE_STATUSES.includes(status)) {
                        if (activeCard) activeCard.style.display = 'block';
                        if (resolvedCard) resolvedCard.style.display = 'none';
                        if (normalCard) normalCard.style.display = 'none';

                        const idEl = document.getElementById('parent-sos-id');
                        if (idEl) idEl.textContent = data.incident_id;
                        const locEl = document.getElementById('parent-sos-location');
                        if (locEl) locEl.textContent = data.location || 'Campus Safe Zone';
                        const timeEl = document.getElementById('parent-sos-time');
                        if (timeEl && data.created_at) timeEl.textContent = data.created_at;
                        const stEl = document.getElementById('parent-sos-status');
                        if (stEl) stEl.textContent = `${status} • Unit: ${data.assigned_responder || 'Quick Response Team'}`;
                    } else if (COMPLETED_STATUSES.includes(status)) {
                        if (activeCard) activeCard.style.display = 'none';
                        if (resolvedCard) resolvedCard.style.display = 'block';
                        if (normalCard) normalCard.style.display = 'none';

                        const rId = document.getElementById('parent-resolved-id');
                        if (rId) rId.textContent = data.incident_id;
                        const rLoc = document.getElementById('parent-resolved-location');
                        if (rLoc) rLoc.textContent = data.location || 'Campus Safe Zone';
                        const rTime = document.getElementById('parent-resolved-time');
                        if (rTime) rTime.textContent = data.resolved_at || data.closed_at || data.updated_at || 'Recently';
                        const rUnit = document.getElementById('parent-resolved-unit');
                        if (rUnit) rUnit.textContent = data.assigned_responder || 'Campus Security';
                    } else {
                        if (activeCard) activeCard.style.display = 'none';
                        if (resolvedCard) resolvedCard.style.display = 'none';
                        if (normalCard) normalCard.style.display = 'block';
                    }
                } else {
                    if (activeCard) activeCard.style.display = 'none';
                    if (resolvedCard) resolvedCard.style.display = 'none';
                    if (normalCard) normalCard.style.display = 'block';
                }
            } catch (err) {
                console.warn("[CampusGuard Parent Safety] Sync error:", err);
            }
        }

        if (typeof io !== 'undefined') {
            try {
                const socket = io();
                socket.on('emergency_status_update', function () {
                    syncParentSafety();
                });
            } catch (e) {}
        }

        window.addEventListener('focus', syncParentSafety);
        window.addEventListener('pageshow', syncParentSafety);
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) syncParentSafety();
        });

        setInterval(syncParentSafety, 3000);
        syncParentSafety();
    };


    // -----------------------------------------------------------------------
    // 8. Admin Safety Control Center & Active SOS Real-Time Stream
    // -----------------------------------------------------------------------
    let activeEmergencyPoller = null;
    let lastKnownEmergencyCount = null;

    function renderStatusBadge(status) {
        if (status === 'TRIGGERED' || status === 'ACTIVE') {
            return '<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); font-weight: 700;">🚨 TRIGGERED</span>';
        } else if (status === 'ACKNOWLEDGED') {
            return '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.4); font-weight: 700;">⚠️ ACKNOWLEDGED</span>';
        } else if (['RESPONDING', 'RESPONDER_ASSIGNED', 'ASSIGNED', 'EN_ROUTE'].includes(status)) {
            return '<span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.4); font-weight: 700;">🚑 EN ROUTE</span>';
        } else if (status === 'ON_SCENE') {
            return '<span class="badge" style="background: rgba(192, 132, 252, 0.2); color: #e9d5ff; border: 1px solid rgba(192, 132, 252, 0.4); font-weight: 700;">📍 ON SCENE</span>';
        } else if (status === 'RESOLVED') {
            return '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.4); font-weight: 700;">✓ RESOLVED</span>';
        } else if (status === 'CLOSED') {
            return '<span class="badge" style="background: rgba(100, 116, 139, 0.25); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.4);">CLOSED</span>';
        }
        return `<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fcd34d;">${escapeHtml(status)}</span>`;
    }

    function renderSeverityBadge(severity) {
        const s = (severity || 'HIGH').toUpperCase();
        if (s === 'CRITICAL') {
            return '<span class="badge" style="background: rgba(239, 68, 68, 0.25); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.5); font-size: 0.7rem; padding: 2px 6px;">CRITICAL</span>';
        } else if (s === 'HIGH') {
            return '<span class="severity-badge-high" style="font-size: 0.7rem; padding: 2px 6px;">HIGH</span>';
        } else if (s === 'MEDIUM') {
            return '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fcd34d; font-size: 0.7rem; padding: 2px 6px;">MEDIUM</span>';
        }
        return '<span class="badge" style="background: rgba(100, 116, 139, 0.2); color: #cbd5e1; font-size: 0.7rem; padding: 2px 6px;">LOW</span>';
    }

    function renderActionButton(inc) {
        const status = inc.status;
        let nextStatus = 'ACKNOWLEDGED';
        let btnText = 'Acknowledge';
        let btnBg = '#f59e0b';

        if (status === 'TRIGGERED' || status === 'ACTIVE') {
            nextStatus = 'ACKNOWLEDGED';
            btnText = 'Acknowledge';
            btnBg = '#f59e0b';
        } else if (status === 'ACKNOWLEDGED') {
            nextStatus = 'EN_ROUTE';
            btnText = 'Dispatch QRT';
            btnBg = '#38bdf8';
        } else if (['RESPONDING', 'RESPONDER_ASSIGNED', 'ASSIGNED', 'EN_ROUTE'].includes(status)) {
            nextStatus = 'ON_SCENE';
            btnText = 'Mark On Scene';
            btnBg = '#a855f7';
        } else if (status === 'ON_SCENE') {
            nextStatus = 'RESOLVED';
            btnText = 'Resolve';
            btnBg = '#10b981';
        } else {
            nextStatus = 'RESOLVED';
            btnText = 'Resolve';
            btnBg = '#10b981';
        }

        return `
            <div style="display: inline-flex; gap: 6px; align-items: center;">
                <a href="/emergency/incident/${escapeHtml(inc.incident_id || inc.emergency_id)}" class="btn-secondary" style="padding: 5px 10px; font-size: 0.76rem;" title="View Dossier">
                    Dossier &rarr;
                </a>
                <form method="POST" action="/admin/sos/status-update" style="display: inline-flex; gap: 6px;">
                    <input type="hidden" name="incident_id" value="${escapeHtml(inc.incident_id || inc.emergency_id)}">
                    <input type="hidden" name="new_status" value="${nextStatus}">
                    <button type="submit" class="btn-primary" style="padding: 6px 12px; font-size: 0.78rem; background: ${btnBg};">${btnText}</button>
                </form>
            </div>
        `;
    }

    async function syncAdminActiveSOS() {
        try {
            const resp = await fetch('/api/admin/sos/active?t=' + Date.now(), { cache: 'no-store' });
            if (!resp.ok) return;
            const data = await resp.json();

            const emergencies = data.emergencies || data.active_sos || [];
            const count = emergencies.length;

            // Audio Alert on new active emergency
            if (lastKnownEmergencyCount !== null && count > lastKnownEmergencyCount) {
                window.playEmergencyAlertSound();
            }
            lastKnownEmergencyCount = count;

            // 1. Update Badges
            const activeCountEl = document.getElementById('active-emergency-count');
            const activeCountNum = document.getElementById('active-sos-count-num');
            if (activeCountNum) activeCountNum.textContent = count;
            if (activeCountEl && !activeCountNum) {
                activeCountEl.innerHTML = `<span class="beacon-dot"></span> ${count} Active Alert${count === 1 ? '' : 's'}`;
            }

            const dashBadge = document.getElementById('dashboard-active-sos-badge');
            if (dashBadge) dashBadge.textContent = `${count} Active Distress`;

            const dashBannerCount = document.getElementById('dashboard-banner-active-sos-count');
            if (dashBannerCount) dashBannerCount.textContent = `${count} Active SOS`;

            // 2. Render Admin Safety Active Table
            const tbody = document.getElementById('admin-active-sos-tbody');
            const emptyState = document.getElementById('admin-active-sos-empty');

            if (tbody) {
                if (count === 0) {
                    tbody.innerHTML = '';
                    if (emptyState) emptyState.style.display = 'block';
                } else {
                    if (emptyState) emptyState.style.display = 'none';
                    tbody.innerHTML = emergencies.map(inc => {
                        const gpsHtml = (inc.latitude && inc.longitude)
                            ? `<div style="font-size: 0.72rem; color: #38bdf8; font-family: var(--font-mono);">GPS: ${Number(inc.latitude).toFixed(4)}, ${Number(inc.longitude).toFixed(4)}</div>`
                            : '';
                        return `
                            <tr id="sos-row-${escapeHtml(inc.incident_id || inc.emergency_id)}" style="border-bottom: 1px solid rgba(255, 255, 255, 0.04);">
                                <td style="padding: 14px 10px; font-family: var(--font-mono); font-weight: 700; color: #818cf8;">
                                    <a href="/emergency/incident/${escapeHtml(inc.incident_id || inc.emergency_id)}" style="color: inherit; text-decoration: none;">
                                        ${escapeHtml(inc.incident_id || inc.emergency_id)}
                                    </a>
                                </td>
                                <td style="padding: 14px 10px;">
                                    <strong style="color: #fff;">${escapeHtml(inc.student_name || inc.reporter_name || 'Campus User')}</strong>
                                    <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(inc.register_number || inc.student_phone || '-')}</div>
                                </td>
                                <td style="padding: 14px 10px;">
                                    <div style="color: var(--text-primary); font-weight: 600;">${escapeHtml(inc.location || inc.campus_zone || 'Campus Perimeter')}</div>
                                    ${gpsHtml}
                                </td>
                                <td style="padding: 14px 10px;">
                                    <div style="color: #fbbf24; font-weight: 600;">${escapeHtml(inc.category || inc.emergency_type || 'Personal Safety')}</div>
                                    ${renderSeverityBadge(inc.severity)}
                                </td>
                                <td style="padding: 14px 10px;">
                                    ${renderStatusBadge(inc.status)}
                                </td>
                                <td style="padding: 14px 10px; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">${escapeHtml(inc.created_at || '')}</td>
                                <td style="padding: 14px 10px; text-align: right;">
                                    ${renderActionButton(inc)}
                                </td>
                            </tr>
                        `;
                    }).join('');
                }
            }

            // 3. Render Dashboard Active Table (if present)
            const dashTbody = document.getElementById('dashboard-active-sos-tbody');
            const dashEmpty = document.getElementById('dashboard-active-sos-empty');
            if (dashTbody) {
                if (count === 0) {
                    dashTbody.innerHTML = '';
                    if (dashEmpty) dashEmpty.style.display = 'block';
                } else {
                    if (dashEmpty) dashEmpty.style.display = 'none';
                    dashTbody.innerHTML = emergencies.map(inc => `
                        <tr id="dashboard-sos-row-${escapeHtml(inc.incident_id || inc.emergency_id)}" style="border-bottom: 1px solid rgba(255, 255, 255, 0.04);">
                            <td style="padding: 14px 10px; font-family: var(--font-mono); font-weight: 700; color: #818cf8;">
                                <a href="/emergency/incident/${escapeHtml(inc.incident_id || inc.emergency_id)}" style="color: inherit; text-decoration: none;">
                                    ${escapeHtml(inc.incident_id || inc.emergency_id)}
                                </a>
                            </td>
                            <td style="padding: 14px 10px;">
                                <strong style="color: var(--text-primary);">${escapeHtml(inc.student_name || inc.reporter_name || 'Campus User')}</strong>
                                <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(inc.register_number || '-')}</div>
                            </td>
                            <td style="padding: 14px 10px; color: var(--text-secondary);">${escapeHtml(inc.location || inc.campus_zone || 'Campus Perimeter')}</td>
                            <td style="padding: 14px 10px;">
                                ${renderStatusBadge(inc.status)}
                            </td>
                            <td style="padding: 14px 10px; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">${escapeHtml(inc.created_at || '')}</td>
                            <td style="padding: 14px 10px; text-align: right;">
                                ${renderActionButton(inc)}
                            </td>
                        </tr>
                    `).join('');
                }
            }

        } catch (err) {
            console.warn("[CampusGuard Admin Active SOS] Sync error:", err);
        }
    }

    // -----------------------------------------------------------------------
    // History Filter & Search Handler
    // -----------------------------------------------------------------------
    let historyFilterTimeout = null;

    window.handleHistoryFilterChange = function () {
        if (historyFilterTimeout) clearTimeout(historyFilterTimeout);
        historyFilterTimeout = setTimeout(() => {
            fetchAndRenderHistory();
        }, 250);
    };

    window.resetHistoryFilters = function () {
        const sInput = document.getElementById('history-search-input');
        const stFilter = document.getElementById('history-status-filter');
        const sevFilter = document.getElementById('history-severity-filter');
        const catFilter = document.getElementById('history-category-filter');

        if (sInput) sInput.value = '';
        if (stFilter) stFilter.value = 'ALL';
        if (sevFilter) sevFilter.value = 'ALL';
        if (catFilter) catFilter.value = 'ALL';

        fetchAndRenderHistory();
    };

    async function fetchAndRenderHistory() {
        const historyTbody = document.getElementById('admin-sos-history-tbody');
        if (!historyTbody) return;

        const sInput = document.getElementById('history-search-input');
        const stFilter = document.getElementById('history-status-filter');
        const sevFilter = document.getElementById('history-severity-filter');
        const catFilter = document.getElementById('history-category-filter');

        const q = sInput ? sInput.value.trim() : '';
        const status = stFilter ? stFilter.value : 'ALL';
        const severity = sevFilter ? sevFilter.value : 'ALL';
        const category = catFilter ? catFilter.value : 'ALL';

        let url = `/api/admin/sos/history?t=${Date.now()}`;
        if (q) url += `&q=${encodeURIComponent(q)}`;
        if (status && status !== 'ALL') url += `&status=${encodeURIComponent(status)}`;
        if (severity && severity !== 'ALL') url += `&severity=${encodeURIComponent(severity)}`;
        if (category && category !== 'ALL') url += `&category=${encodeURIComponent(category)}`;

        try {
            const resp = await fetch(url, { cache: 'no-store' });
            if (!resp.ok) return;
            const data = await resp.json();

            const historyList = data.history || [];
            const countBadge = document.getElementById('history-count-badge');
            const emptyEl = document.getElementById('admin-sos-history-empty');

            if (countBadge) countBadge.textContent = historyList.length;

            if (historyList.length === 0) {
                historyTbody.innerHTML = '';
                if (emptyEl) emptyEl.style.display = 'block';
            } else {
                if (emptyEl) emptyEl.style.display = 'none';
                historyTbody.innerHTML = historyList.map(inc => {
                    const trigTime = (inc.created_at || '').substring(0, 16) || '-';
                    const resTime = (inc.resolved_at || inc.closed_at || '').substring(0, 16) || '-';

                    return `
                        <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.04);">
                            <td style="padding: 12px 10px; font-family: var(--font-mono); font-weight: 700; color: #818cf8;">
                                <a href="/emergency/incident/${escapeHtml(inc.incident_id || inc.emergency_id)}" style="color: inherit; text-decoration: none;">
                                    ${escapeHtml(inc.incident_id || inc.emergency_id)}
                                </a>
                            </td>
                            <td style="padding: 12px 10px;">
                                <strong style="color: var(--text-primary);">${escapeHtml(inc.student_name || inc.reporter_name || 'Campus User')}</strong>
                                <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(inc.register_number || inc.student_phone || '-')}</div>
                            </td>
                            <td style="padding: 12px 10px;">
                                <div style="color: #cbd5e1; font-weight: 600;">${escapeHtml(inc.category || inc.emergency_type || 'General Emergency')}</div>
                                ${renderSeverityBadge(inc.severity)}
                            </td>
                            <td style="padding: 12px 10px; color: var(--text-secondary);">
                                ${escapeHtml(inc.location || inc.campus_zone || 'Campus Safe Zone')}
                            </td>
                            <td style="padding: 12px 10px; color: var(--text-muted); font-size: 0.78rem; font-family: var(--font-mono);">
                                ${escapeHtml(trigTime)}
                            </td>
                            <td style="padding: 12px 10px; color: #34d399; font-size: 0.78rem; font-family: var(--font-mono);">
                                ${escapeHtml(resTime)}
                            </td>
                            <td style="padding: 12px 10px;">
                                ${renderStatusBadge(inc.status)}
                            </td>
                            <td style="padding: 12px 10px; font-size: 0.82rem; color: var(--text-secondary);">
                                ${escapeHtml(inc.assigned_responder || 'Campus QRT')}
                            </td>
                            <td style="padding: 12px 10px; text-align: right;">
                                <a href="/emergency/incident/${escapeHtml(inc.incident_id || inc.emergency_id)}" class="btn-secondary" style="padding: 4px 10px; font-size: 0.76rem;" title="View Dossier">
                                    Dossier &rarr;
                                </a>
                            </td>
                        </tr>
                    `;
                }).join('');
            }
        } catch (err) {
            console.warn("[CampusGuard History SOS] Fetch error:", err);
        }
    }

    // -----------------------------------------------------------------------
    // Admin Safety Master Live Stream Initializer
    // -----------------------------------------------------------------------
    window.initAdminSafetyLiveStream = function () {
        if (typeof io !== 'undefined') {
            try {
                const socket = io();
                socket.on('emergency_status_update', function () {
                    syncAdminActiveSOS();
                    fetchAndRenderHistory();
                });
                socket.on('emergency_new', function () {
                    syncAdminActiveSOS();
                });
                socket.on('sos_alert_triggered', function () {
                    syncAdminActiveSOS();
                });
                socket.on('sos_status_changed', function () {
                    syncAdminActiveSOS();
                    fetchAndRenderHistory();
                });
            } catch (e) {}
        }

        window.addEventListener('focus', () => {
            syncAdminActiveSOS();
            fetchAndRenderHistory();
        });
        window.addEventListener('pageshow', () => {
            syncAdminActiveSOS();
            fetchAndRenderHistory();
        });
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                syncAdminActiveSOS();
                fetchAndRenderHistory();
            }
        });

        if (activeEmergencyPoller) clearInterval(activeEmergencyPoller);
        activeEmergencyPoller = setInterval(() => {
            syncAdminActiveSOS();
        }, 3500);

        syncAdminActiveSOS();
    };

    window.initCommandCenterLiveStream = window.initAdminSafetyLiveStream;

    // -----------------------------------------------------------------------
    // 9. Auto-Initialization on Page Load
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
