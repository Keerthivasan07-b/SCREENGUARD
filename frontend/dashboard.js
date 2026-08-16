/* ═══════════════════════════════════════════════════════════
   ScreenGuard Faculty Dashboard — JavaScript Engine
   Handles WebSocket, live frames, alerts, fullscreen, grid
   ═══════════════════════════════════════════════════════════ */

class ScreenGuardDashboard {
    constructor() {
        // State
        this.ws = null;
        this.students = {};        // { studentId: { name, status, lastFrame, lastSeen, fps } }
        this.alerts = [];
        this.alertCount = 0;
        this.activePopouts = new Map(); // Maps studentId -> { isAlert, reason, detail }
        this.fpsTrackers = {};     // { studentId: { frames: 0, lastCheck: timestamp } }
        this.alertAudio = null;
        this.alertedStudents = new Set();

        // DOM References
        this.dom = {
            connectionStatus: document.getElementById('connectionStatus'),
            studentGrid: document.getElementById('studentGrid'),
            emptyState: document.getElementById('emptyState'),
            alertsList: document.getElementById('alertsList'),
            noAlerts: document.getElementById('noAlerts'),
            studentCount: document.getElementById('studentCount'),
            alertCount: document.getElementById('alertCount'),
            avgFps: document.getElementById('avgFps'),
            searchInput: document.getElementById('searchInput'),
            gridSize: document.getElementById('gridSize'),
            fullscreenOverlay: document.getElementById('fullscreenOverlay'),
            popoutContainer: document.getElementById('popoutContainer'),
            popoutCountBadge: document.getElementById('popoutCountBadge'),
            popoutCloseAll: document.getElementById('popoutCloseAll'),
            fullscreenClose: document.getElementById('fullscreenClose'),
            clearAlerts: document.getElementById('clearAlerts'),
            settingsOverlay: document.getElementById('settingsOverlay'),
            backendUrl: document.getElementById('backendUrl'),
            authToken: document.getElementById('authToken'),
            settingsConnect: document.getElementById('settingsConnect'),
            settingsCancel: document.getElementById('settingsCancel'),
        };

        this.initEventListeners();
        this.initAlertSound();

        // Try auto-connect from localStorage, otherwise show settings
        const savedUrl = localStorage.getItem('sg_backend_url');
        const savedToken = localStorage.getItem('sg_auth_token');
        if (savedUrl) {
            this.dom.backendUrl.value = savedUrl;
            this.dom.authToken.value = savedToken || 'faculty-secret';
            this.dom.settingsOverlay.classList.add('hidden');
            this.connect(savedUrl, savedToken || 'faculty-secret');
        }
    }

    // ── Event Listeners ─────────────────────────────────
    initEventListeners() {
        // Settings modal
        this.dom.connectionStatus.addEventListener('click', () => {
            this.dom.settingsOverlay.classList.remove('hidden');
        });

        this.dom.settingsConnect.addEventListener('click', () => {
            const url = this.dom.backendUrl.value.trim();
            const token = this.dom.authToken.value.trim();
            if (url) {
                localStorage.setItem('sg_backend_url', url);
                localStorage.setItem('sg_auth_token', token);
                this.dom.settingsOverlay.classList.add('hidden');
                this.connect(url, token);
            }
        });

        this.dom.settingsCancel.addEventListener('click', () => {
            if (this.ws) {
                this.dom.settingsOverlay.classList.add('hidden');
            }
        });

        // Grid column selector
        this.dom.gridSize.addEventListener('change', (e) => {
            this.dom.studentGrid.style.gridTemplateColumns = `repeat(${e.target.value}, 1fr)`;
        });

        // Search
        this.dom.searchInput.addEventListener('input', (e) => {
            this.filterStudents(e.target.value.toLowerCase());
        });

        // Popout overlay controls
        if (this.dom.fullscreenClose) {
            this.dom.fullscreenClose.addEventListener('click', () => this.closeAllPopouts());
        }
        if (this.dom.popoutCloseAll) {
            this.dom.popoutCloseAll.addEventListener('click', () => this.closeAllPopouts());
        }
        this.dom.fullscreenOverlay.addEventListener('click', (e) => {
            if (e.target === this.dom.fullscreenOverlay) this.closeAllPopouts();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeAllPopouts();
        });

        // Clear alerts
        this.dom.clearAlerts.addEventListener('click', () => {
            this.alerts = [];
            this.alertCount = 0;
            this.alertedStudents.clear();
            this.dom.alertCount.textContent = '0';
            this.dom.alertsList.innerHTML = '';
            this.dom.noAlerts.style.display = 'flex';
            // Remove alert styling from cards
            document.querySelectorAll('.student-card.alert-active').forEach(card => {
                card.classList.remove('alert-active');
                const badge = card.querySelector('.alert-badge');
                if (badge) badge.remove();
            });
            // Automatically close all alert screen popouts
            this.closeAllPopouts();
        });

        // FPS calculator interval
        setInterval(() => this.calculateFps(), 3000);
    }

    // ── Alert Sound ─────────────────────────────────────
    initAlertSound() {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.audioCtx = audioCtx;
        } catch (e) {
            console.warn('AudioContext not available');
        }
    }

    playAlertSound() {
        if (!this.audioCtx) return;
        try {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            osc.frequency.setValueAtTime(880, this.audioCtx.currentTime);
            osc.frequency.setValueAtTime(660, this.audioCtx.currentTime + 0.1);
            osc.frequency.setValueAtTime(880, this.audioCtx.currentTime + 0.2);
            gain.gain.setValueAtTime(0.3, this.audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.5);
            osc.start();
            osc.stop(this.audioCtx.currentTime + 0.5);
        } catch (e) {
            // Audio might fail on first interaction
        }
    }

    // ── WebSocket Connection ────────────────────────────
    connect(url, authToken) {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        this.setConnectionStatus('connecting', 'Connecting...');

        try {
            this.ws = new WebSocket(url);
        } catch (e) {
            this.setConnectionStatus('disconnected', 'Invalid URL');
            return;
        }

        this.ws.onopen = () => {
            console.log('[ScreenGuard] WebSocket connected');
            // Send faculty registration
            this.ws.send(JSON.stringify({
                type: 'register',
                role: 'faculty',
                authToken: authToken
            }));
            this.setConnectionStatus('connected', 'Connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('[ScreenGuard] Error parsing message:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('[ScreenGuard] WebSocket disconnected');
            this.setConnectionStatus('disconnected', 'Disconnected');
            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
                    this.connect(url, authToken);
                }
            }, 3000);
        };

        this.ws.onerror = (err) => {
            console.error('[ScreenGuard] WebSocket error:', err);
            this.setConnectionStatus('disconnected', 'Error');
        };
    }

    // ── Message Router ──────────────────────────────────
    handleMessage(data) {
        switch (data.type) {
            case 'roster':
                this.handleRoster(data);
                break;
            case 'frame':
                this.handleFrame(data);
                break;
            case 'alert':
                this.handleAlert(data);
                break;
            case 'clear_alert':
                this.handleClearAlert(data);
                break;
            default:
                console.log('[ScreenGuard] Unknown message type:', data.type);
        }
    }

    // ── Device Role Filter ──────────────────────────────
    isFacultyDevice(studentId, studentName = '') {
        const lowerId = (studentId || '').toLowerCase();
        const lowerName = (studentName || '').toLowerCase();
        const keywords = ['faculty', 'teacher', 'instructor', 'professor', 'admin', 'host'];
        return keywords.some(k => lowerId.includes(k) || lowerName.includes(k));
    }

    // ── Roster Update ───────────────────────────────────
    handleRoster(data) {
        const incomingIds = new Set();

        (data.students || []).forEach(s => {
            // Exclude faculty or host machines from student roster
            if (this.isFacultyDevice(s.studentId, s.studentName)) return;

            incomingIds.add(s.studentId);
            if (!this.students[s.studentId]) {
                this.students[s.studentId] = {
                    name: s.studentName || s.studentId,
                    status: s.status || 'online',
                    lastFrame: null,
                    lastSeen: Date.now()
                };
                this.createStudentCard(s.studentId);
            } else {
                this.students[s.studentId].name = s.studentName || s.studentId;
                this.students[s.studentId].status = s.status || 'online';
                this.updateStudentCardStatus(s.studentId);
            }
        });

        this.dom.studentCount.textContent = incomingIds.size;
        this.updateEmptyState();
    }

    // ── Frame Update ────────────────────────────────────
    handleFrame(data) {
        const studentId = data.studentId;
        if (!studentId || this.isFacultyDevice(studentId)) return;

        // Auto-create student entry if roster hasn't arrived yet
        if (!this.students[studentId]) {
            this.students[studentId] = {
                name: studentId,
                status: 'online',
                lastFrame: null,
                lastSeen: Date.now()
            };
            this.createStudentCard(studentId);
            this.updateEmptyState();
        }

        // Track FPS
        if (!this.fpsTrackers[studentId]) {
            this.fpsTrackers[studentId] = { frames: 0, lastCheck: Date.now() };
        }
        this.fpsTrackers[studentId].frames++;

        // Update student state
        this.students[studentId].lastFrame = data.data;
        this.students[studentId].lastSeen = Date.now();
        this.students[studentId].status = 'online';

        // Update grid card image
        const card = document.getElementById(`card-${studentId}`);
        if (card) {
            const img = card.querySelector('.card-screen img');
            const noFrame = card.querySelector('.no-frame');
            if (img && data.data) {
                img.src = `data:image/jpeg;base64,${data.data}`;
                img.style.display = 'block';
                if (noFrame) noFrame.style.display = 'none';
            }
            this.updateStudentCardStatus(studentId);
        }

        // Update parallel pop-out screen image if active in popout modal
        if (this.activePopouts.has(studentId) && data.data) {
            const popoutImg = document.getElementById(`popout-img-${studentId}`);
            if (popoutImg) {
                popoutImg.src = `data:image/jpeg;base64,${data.data}`;
            }
        }

        this.dom.studentCount.textContent = Object.keys(this.students).length;
    }

    // ── Alert Handler ───────────────────────────────────
    handleAlert(data) {
        if (this.isFacultyDevice(data.studentId, data.studentName)) return;

        this.alertCount++;
        this.dom.alertCount.textContent = this.alertCount;

        const alertItem = {
            studentId: data.studentId,
            studentName: data.studentName || this.students[data.studentId]?.name || data.studentId,
            reason: data.reason,
            detail: data.detail,
            severity: data.severity || 'high',
            timestamp: data.timestamp || Date.now()
        };

        this.alerts.unshift(alertItem);
        if (this.alerts.length > 50) this.alerts.pop();

        // Add to sidebar
        this.addAlertToSidebar(alertItem);

        // Mark student card as alerted
        this.markStudentAlert(data.studentId);

        // Play alarm sound
        this.playAlertSound();

        // Pop out screen side-by-side (parallel view for multi-alerts)
        this.openPopout(data.studentId, true, alertItem);
    }

    // ── Clear Alert Handler (Pop In) ──────────────────────
    handleClearAlert(data) {
        const studentId = data.studentId;
        if (!studentId) return;

        // Instantly pop in / remove the popout screen modal for this student
        this.removePopout(studentId);

        // Remove red alert highlight & badge from student grid card
        const card = document.getElementById(`card-${studentId}`);
        if (card) {
            card.classList.remove('alert-active');
            const badge = card.querySelector('.alert-badge');
            if (badge) badge.remove();
        }
        this.alertedStudents.delete(studentId);
    }

    // ── UI: Create Student Card ─────────────────────────
    createStudentCard(studentId) {
        const student = this.students[studentId];
        const card = document.createElement('div');
        card.id = `card-${studentId}`;
        card.className = `student-card ${student.status === 'offline' ? 'offline' : ''}`;

        card.innerHTML = `
            <div class="card-screen">
                <img style="display:none" alt="${student.name} screen">
                <div class="no-frame">
                    <span>🖥️</span>
                    Waiting for frame...
                </div>
            </div>
            <div class="card-info">
                <div class="card-identity">
                    <span class="card-name">${student.name}</span>
                    <span class="card-id">${studentId}</span>
                </div>
                <div class="card-status">
                    <span class="card-status-dot ${student.status}"></span>
                    <span class="card-status-label">${student.status}</span>
                </div>
            </div>
        `;

        card.addEventListener('click', () => this.openPopout(studentId, false));
        this.dom.studentGrid.appendChild(card);
    }

    // ── UI: Update Card Status ──────────────────────────
    updateStudentCardStatus(studentId) {
        const card = document.getElementById(`card-${studentId}`);
        const student = this.students[studentId];
        if (!card || !student) return;

        const dot = card.querySelector('.card-status-dot');
        const label = card.querySelector('.card-status-label');
        const name = card.querySelector('.card-name');

        if (dot) {
            dot.className = `card-status-dot ${student.status}`;
        }
        if (label) label.textContent = student.status;
        if (name) name.textContent = student.name;

        if (student.status === 'offline') {
            card.classList.add('offline');
        } else {
            card.classList.remove('offline');
        }
    }

    // ── UI: Mark Student Alert ──────────────────────────
    markStudentAlert(studentId) {
        const card = document.getElementById(`card-${studentId}`);
        if (!card) return;

        card.classList.add('alert-active');
        this.alertedStudents.add(studentId);

        // Add alert badge if not already there
        if (!card.querySelector('.alert-badge')) {
            const badge = document.createElement('div');
            badge.className = 'alert-badge';
            badge.textContent = '⚠ ALERT';
            card.querySelector('.card-screen').appendChild(badge);
        }

        // Auto-remove alert after 15 seconds
        setTimeout(() => {
            card.classList.remove('alert-active');
            this.alertedStudents.delete(studentId);
            const badge = card.querySelector('.alert-badge');
            if (badge) badge.remove();
        }, 15000);
    }

    // ── UI: Add Alert to Sidebar ────────────────────────
    addAlertToSidebar(alert) {
        this.dom.noAlerts.style.display = 'none';

        const time = new Date(alert.timestamp).toLocaleTimeString();
        const el = document.createElement('div');
        el.className = 'alert-item';
        el.innerHTML = `
            <div class="alert-item-header">
                <span class="alert-student">⚠ ${alert.studentName}</span>
                <span class="alert-time">${time}</span>
            </div>
            <div class="alert-detail">${alert.detail}</div>
            <span class="alert-severity ${alert.severity === 'medium' ? 'medium' : ''}">${alert.severity}</span>
        `;

        el.addEventListener('click', () => this.openPopout(alert.studentId, true, alert));

        // Insert at top
        this.dom.alertsList.insertBefore(el, this.dom.alertsList.firstChild);

        // Limit sidebar to 30 items
        while (this.dom.alertsList.children.length > 31) {
            this.dom.alertsList.removeChild(this.dom.alertsList.lastChild);
        }
    }

    // ── Parallel Pop-out Screen View ──────────────────────────────
    openPopout(studentId, isAlert = false, alertDetails = null) {
        if (this.isFacultyDevice(studentId)) return;
        const student = this.students[studentId];
        if (!student) return;

        // Clear existing auto-dismiss timer for this student if any
        const existing = this.activePopouts.get(studentId);
        if (existing && existing.timerId) {
            clearTimeout(existing.timerId);
        }

        let timerId = null;
        if (isAlert) {
            // Auto-dismiss alert popout screen after 15 seconds if no new alerts arrive
            timerId = setTimeout(() => {
                const popInfo = this.activePopouts.get(studentId);
                if (popInfo && popInfo.isAlert) {
                    this.removePopout(studentId);
                }
            }, 15000);
        }

        this.activePopouts.set(studentId, {
            isAlert: isAlert,
            reason: alertDetails?.reason || (isAlert ? 'Alert Triggered' : 'Live Monitor'),
            detail: alertDetails?.detail || '',
            timerId: timerId
        });

        this.renderPopouts();
    }

    removePopout(studentId) {
        const existing = this.activePopouts.get(studentId);
        if (existing && existing.timerId) {
            clearTimeout(existing.timerId);
        }
        this.activePopouts.delete(studentId);
        if (this.activePopouts.size === 0) {
            this.closeAllPopouts();
        } else {
            this.renderPopouts();
        }
    }

    closeAllPopouts() {
        this.activePopouts.forEach(info => {
            if (info.timerId) clearTimeout(info.timerId);
        });
        this.activePopouts.clear();
        this.dom.fullscreenOverlay.classList.remove('active', 'alert-fullscreen');
        if (this.dom.popoutContainer) {
            this.dom.popoutContainer.innerHTML = '';
        }
        if (this.dom.popoutCountBadge) {
            this.dom.popoutCountBadge.textContent = '0 Active Screens';
        }
    }

    renderPopouts() {
        const count = this.activePopouts.size;
        if (count === 0) {
            this.closeAllPopouts();
            return;
        }

        this.dom.fullscreenOverlay.classList.add('active');
        if (this.dom.popoutCountBadge) {
            this.dom.popoutCountBadge.textContent = `${count} Active Screen${count > 1 ? 's' : ''}`;
        }

        // Dynamic parallel layout class
        this.dom.popoutContainer.className = 'popout-content';
        if (count === 1) {
            this.dom.popoutContainer.classList.add('single-card');
        } else if (count === 2) {
            this.dom.popoutContainer.classList.add('two-cards');
        }

        // Render each popout card
        this.dom.popoutContainer.innerHTML = '';
        let hasAnyAlert = false;

        this.activePopouts.forEach((info, sid) => {
            const student = this.students[sid];
            if (!student) return;
            if (info.isAlert) hasAnyAlert = true;

            const cardEl = document.createElement('div');
            cardEl.className = `popout-card ${info.isAlert ? 'is-alert' : ''}`;
            cardEl.id = `popout-card-${sid}`;

            const imgSrc = student.lastFrame ? `data:image/jpeg;base64,${student.lastFrame}` : '';

            cardEl.innerHTML = `
                <div class="popout-card-header">
                    <div class="popout-card-title">
                        <span class="popout-card-name">${student.name}</span>
                        <span class="popout-card-id">${sid}</span>
                    </div>
                    <button class="popout-card-close" title="Close screen">✕</button>
                </div>
                <div class="popout-card-body">
                    <img id="popout-img-${sid}" src="${imgSrc}" alt="${student.name} Screen">
                </div>
                ${info.isAlert ? `
                <div class="popout-card-footer">
                    <span class="popout-reason">⚠️ ${info.reason}</span>
                    <span>${info.detail}</span>
                </div>` : ''}
            `;

            cardEl.querySelector('.popout-card-close').addEventListener('click', (e) => {
                e.stopPropagation();
                this.removePopout(sid);
            });

            this.dom.popoutContainer.appendChild(cardEl);
        });

        if (hasAnyAlert) {
            this.dom.fullscreenOverlay.classList.add('alert-fullscreen');
        } else {
            this.dom.fullscreenOverlay.classList.remove('alert-fullscreen');
        }
    }

    // ── Search / Filter ─────────────────────────────────
    filterStudents(query) {
        Object.keys(this.students).forEach(sid => {
            const card = document.getElementById(`card-${sid}`);
            if (!card) return;
            const student = this.students[sid];
            const match = sid.toLowerCase().includes(query) ||
                         student.name.toLowerCase().includes(query);
            card.style.display = match ? '' : 'none';
        });
    }

    // ── FPS Calculator ──────────────────────────────────
    calculateFps() {
        const now = Date.now();
        let totalFps = 0;
        let count = 0;

        Object.keys(this.fpsTrackers).forEach(sid => {
            const tracker = this.fpsTrackers[sid];
            const elapsed = (now - tracker.lastCheck) / 1000;
            if (elapsed > 0) {
                const fps = tracker.frames / elapsed;
                totalFps += fps;
                count++;
                tracker.frames = 0;
                tracker.lastCheck = now;
            }
        });

        const avgFps = count > 0 ? (totalFps / count).toFixed(1) : '0';
        this.dom.avgFps.textContent = avgFps;
    }

    // ── UI: Empty State Toggle ──────────────────────────
    updateEmptyState() {
        const hasStudents = Object.keys(this.students).length > 0;
        if (this.dom.emptyState) {
            this.dom.emptyState.style.display = hasStudents ? 'none' : 'flex';
        }
    }

    // ── Connection Status UI ────────────────────────────
    setConnectionStatus(state, label) {
        const dot = this.dom.connectionStatus.querySelector('.status-dot');
        const statusLabel = this.dom.connectionStatus.querySelector('.status-label');

        dot.className = `status-dot ${state}`;
        statusLabel.textContent = label;
    }
}

// ── Initialize Dashboard ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new ScreenGuardDashboard();
});
