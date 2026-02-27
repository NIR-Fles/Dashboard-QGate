// --- Configuration & State ---
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.host;
const WS_URL = `${protocol}//${host}/ws`;
const API_URL = `${window.location.protocol}//${host}/api`;

let historyData = [];
let selectedHistoryItem = null;
let currentHistoryCamera = 'right';

// Bolt Configuration (for history filtering)
const boltHierarchy = {
    right: [
        "NUT_FLANGE_6MM_GROUNDING", "BOLT_FIXING_RADIATOR_RESERVE", "BOLT_AXLE_FRONT_WHEEL",
        "BF_10X55_LINK_ASSY_ENG_HANGER_R", "BF_10X38_REAR_CUSHION_R", "BF_10X65_MUFFLER_CENTER_UPPER",
        "BF_10X65_MUFFLER_REAR_UNDER", "BF_10X65_MUFFLER_FRONT_UNDER"
    ],
    upper: [
        "BS_6X18_FENDER_C_REAR_FRONT", "BS_6X18_FENDER_C_REAR_REAR"
    ],
    left: [
        "NUT_FRONT_AXLE_12MM", "BOLT_TORX_8X28_CALIPER_UNDER", "BOLT_TORX_8X28_CALIPER_UPPER",
        "BF_8X12_HORN_COMP", "BOLT_SIDE_STAND_PIVOT", "BF_6X12_CLAMP_THROTTLE_CABLE",
        "BF_10X55_LINK_ASSY_ENG_HANGER_L", "BF_10X38_REAR_CUSHION_L", "BOLT_WASHER_6X12_REAR_FENDER",
        "BF_10X255_LINK_ASSY_ENG_HANGER_L"
    ]
};

// DOM Elements
const elements = {
    date: document.getElementById('date'),
    time: document.getElementById('time'),
    tabs: {
        monitoring: document.getElementById('monitoring-tab'),
        history: document.getElementById('history-tab')
    },
    navBtns: {
        monitoring: document.getElementById('btn-monitoring'),
        history: document.getElementById('btn-history')
    },
    monitoring: {
        finalResult: document.getElementById('final-result'),
        images: {
            right_step1: document.getElementById('img-right-step1'),
            right_step2: document.getElementById('img-right-step2'),
            upper_step1: document.getElementById('img-upper-step1'),
            upper_step2: document.getElementById('img-upper-step2'),
            left_step1: document.getElementById('img-left-step1'),
            left_step2: document.getElementById('img-left-step2'),
        },
        headers: {
            right: document.getElementById('header-status-right'),
            upper: document.getElementById('header-status-upper'),
            left: document.getElementById('header-status-left'),
        }
    },
    history: {
        tbody: document.getElementById('history-tbody'),
        search: document.getElementById('search-frame-id'),
        filterFrom: document.getElementById('filter-from'),
        filterTo: document.getElementById('filter-to'),
        details: {
            frame: document.getElementById('hist-detail-frame'),
            model: document.getElementById('hist-detail-model'),
            date: document.getElementById('hist-detail-date'),
            result: document.getElementById('hist-detail-result'),
            list: document.getElementById('hist-inspection-list'),
            camTitle: document.getElementById('hist-cam-title'),
            camStatus: document.getElementById('hist-cam-status'),
            image1: document.getElementById('hist-image-step1'),
            image2: document.getElementById('hist-image-step2')
        }
    }
};

// --- Tab Switching ---
function switchTab(tabId) {
    Object.values(elements.tabs).forEach(tab => tab.classList.remove('active'));
    Object.values(elements.navBtns).forEach(btn => btn.classList.remove('active'));

    elements.tabs[tabId].classList.add('active');
    elements.navBtns[tabId].classList.add('active');

    if (tabId === 'history') {
        loadHistory();
    }
}

// --- WebSocket Monitoring ---
function connectWebSocket() {
    const socket = new WebSocket(WS_URL);
    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateMonitoringDashboard(data);
        } catch (e) {
            console.error("WS Error:", e);
        }
    };
    socket.onclose = () => setTimeout(connectWebSocket, 3000);
}

function updateMonitoringDashboard(state) {
    if (!elements.tabs.monitoring.classList.contains('active')) return;

    try {
        // 1. Update Images
        if (state.images) {
            for (const [key, b64] of Object.entries(state.images)) {
                const imgEl = elements.monitoring.images[key];
                if (imgEl) {
                    imgEl.src = b64 || "";
                }
            }
        }

        // 2. Update Bolt Statuses
        if (state.statuses) {
            for (const [boltId, status] of Object.entries(state.statuses)) {
                const statusSpan = document.getElementById(`status-${boltId}`);
                if (statusSpan) {
                    if (statusSpan.textContent !== status) {
                        statusSpan.textContent = status;
                        statusSpan.className = `item-status ${status.toLowerCase()}`;
                        if (status === '-') statusSpan.className = 'item-status pending';
                    }
                }
            }
        }

        // 3. Update Station Headers
        ['right', 'upper', 'left'].forEach(side => {
            const listEl = document.getElementById(`list-${side}`);
            const headerEl = elements.monitoring.headers[side];
            if (listEl && headerEl) {
                const currentStatuses = Array.from(listEl.querySelectorAll('.item-status')).map(s => s.textContent);

                let sectionStatus = '-';
                if (currentStatuses.includes('NG')) sectionStatus = 'NG';
                else if (currentStatuses.every(s => s === 'OK')) sectionStatus = 'OK';

                if (headerEl.textContent !== sectionStatus) {
                    headerEl.textContent = sectionStatus;
                    headerEl.className = `column-status ${sectionStatus.toLowerCase()}`;
                    if (sectionStatus === '-') headerEl.className = 'column-status pending';
                }
            }
        });

        // 4. Update Final Result
        if (state.system) {
            const final = state.system.final_result;
            const resEl = elements.monitoring.finalResult;
            if (resEl && resEl.textContent !== final) {
                resEl.textContent = final;
                resEl.className = `result-display ${final.toLowerCase()}`;
                if (final === '-') resEl.className = 'result-display pending';
            }

            // 5. Update Frame Name / Model
            const frameEl = document.getElementById('monitoring-frame-id');
            const modelEl = document.getElementById('monitoring-model-name');
            if (frameEl) frameEl.textContent = state.system.frame_id || state.system.current_frame_id || "-";
            if (modelEl) modelEl.textContent = state.system.model || "-";
        }
    } catch (err) {
        console.error("Dashboard Update Error:", err);
    }
}

// --- History Logic ---
async function loadHistory() {
    try {
        const response = await fetch(`${API_URL}/history`);
        const json = await response.json();
        if (json.status === 'success') {
            historyData = json.data;
            renderHistoryTable();
        }
    } catch (e) {
        console.error("Failed to load history:", e);
    }
}

function renderHistoryTable() {
    const searchTerm = elements.history.search.value.toLowerCase().trim();
    const fromDate = elements.history.filterFrom.value;
    const toDate = elements.history.filterTo.value;

    console.log(`Filtering: search="${searchTerm}", from="${fromDate}", to="${toDate}"`);

    elements.history.tbody.innerHTML = '';

    const filtered = historyData.filter(item => {
        // Search Filter
        const matchesSearch = !searchTerm || item.frame_id.toLowerCase().includes(searchTerm);

        // Date Filters
        let matchesDate = true;

        if (fromDate || toDate) {
            const itemTime = new Date(item.check_time).getTime();
            if (fromDate && itemTime < new Date(fromDate).getTime()) matchesDate = false;
            if (toDate && itemTime > new Date(toDate).getTime()) matchesDate = false;
        }

        return matchesSearch && matchesDate;
    });

    console.log(`Filtered items: ${filtered.length}`);

    filtered.forEach(item => {
        const tr = document.createElement('tr');
        if (selectedHistoryItem && selectedHistoryItem.id === item.id) tr.classList.add('selected');
        tr.innerHTML = `
            <td>${item.id}</td>
            <td>${item.frame_id}</td>
            <td>${item.model}</td>
            <td>${item.check_time}</td>
        `;
        tr.onclick = () => selectHistoryItem(item, tr);
        elements.history.tbody.appendChild(tr);
    });
}

function selectHistoryItem(item, rowEl) {
    selectedHistoryItem = item;

    // UI selection
    Array.from(elements.history.tbody.querySelectorAll('tr')).forEach(tr => tr.classList.remove('selected'));
    rowEl.classList.add('selected');

    // Update Detail Header
    elements.history.details.frame.textContent = item.frame_id;
    elements.history.details.model.textContent = item.model;
    elements.history.details.date.textContent = item.check_time;

    const res = item.final_result;
    elements.history.details.result.textContent = res;
    elements.history.details.result.className = `result-display ${res.toLowerCase()}`;

    updateHistoryDetailPanel();
}

function updateHistoryDetailPanel() {
    if (!selectedHistoryItem) return;

    const side = currentHistoryCamera;
    elements.history.details.camTitle.textContent = `${side.charAt(0).toUpperCase() + side.slice(1)} Camera`;

    // Filter bolts for this side
    const boltsOnThisSide = boltHierarchy[side];
    elements.history.details.list.innerHTML = '';

    let sideOk = true;
    boltsOnThisSide.forEach((boltId, index) => {
        const status = selectedHistoryItem.bolt_data[boltId] || '-';
        if (status !== 'OK') sideOk = false;

        const li = document.createElement('li');
        li.innerHTML = `
            <span class="item-index">${index + 1}</span>
            <span class="item-name">${boltId.replace(/_/g, ' ')}</span>
            <span class="item-status ${status.toLowerCase()}">${status}</span>
        `;
        elements.history.details.list.appendChild(li);
    });

    // Side Status
    const sideStatus = sideOk ? 'OK' : 'NG';
    elements.history.details.camStatus.textContent = sideStatus;
    elements.history.details.camStatus.className = `column-status ${sideStatus.toLowerCase()}`;

    // Update Images
    const img1 = selectedHistoryItem.images[`${side}_step1`];
    const img2 = selectedHistoryItem.images[`${side}_step2`];

    elements.history.details.image1.src = img1 ? `/history_images/${img1}` : "";
    elements.history.details.image2.src = img2 ? `/history_images/${img2}` : "";
}

// --- Utils ---
function updateDateTime() {
    const now = new Date();
    elements.date.textContent = now.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    elements.time.textContent = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);
    connectWebSocket();

    // Event Listeners
    elements.navBtns.monitoring.onclick = () => switchTab('monitoring');
    elements.navBtns.history.onclick = () => switchTab('history');

    // Search and Filter Listeners
    elements.history.search.addEventListener('input', renderHistoryTable);
    elements.history.search.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            console.log("Search Enter pressed");
            renderHistoryTable();
        }
    });
    elements.history.filterFrom.addEventListener('change', renderHistoryTable);
    elements.history.filterTo.addEventListener('change', renderHistoryTable);

    // Camera Navigation Buttons
    document.querySelectorAll('.cam-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.cam-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentHistoryCamera = btn.dataset.cam;
            updateHistoryDetailPanel();
        };
    });
});

