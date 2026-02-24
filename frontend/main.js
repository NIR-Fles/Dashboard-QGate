// Backend WebSocket URL
// Automatically determine host based on where the page is served from
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.host; // e.g., "localhost:8000" or "192.168.1.50:8000"
const WS_URL = `${protocol}//${host}/ws`;

// Static Bolt Configuration (Obsoleted by static HTML)
// const boltData = { ... };

// DOM Elements
const elements = {
    date: document.getElementById('date'),
    time: document.getElementById('time'),
    finalResult: document.getElementById('final-result'),
    images: {
        right_step1: document.getElementById('img-right-step1'),
        right_step2: document.getElementById('img-right-step2'),
        upper_step1: document.getElementById('img-upper-step1'),
        upper_step2: document.getElementById('img-upper-step2'),
        left_step1: document.getElementById('img-left-step1'),
        left_step2: document.getElementById('img-left-step2'),
    },
    lists: {
        right: document.getElementById('list-right'),
        upper: document.getElementById('list-upper'),
        left: document.getElementById('list-left'),
    },
    headers: {
        right: document.getElementById('header-status-right'),
        upper: document.getElementById('header-status-upper'),
        left: document.getElementById('header-status-left'),
    }
};

// initLists removed as lists are now static in HTML

function connectWebSocket() {
    console.log("Connecting to WebSocket...");
    const socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        console.log("WebSocket Connected");
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        } catch (e) {
            console.error("Error parsing WS message:", e);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket Disconnected. Reconnecting in 3s...");
        setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (err) => {
        console.error("WebSocket Error:", err);
        socket.close();
    };
}

function updateDashboard(state) {
    // 1. Update Images
    for (const [key, b64] of Object.entries(state.images)) {
        const imgEl = elements.images[key];
        if (imgEl) {
            if (b64) {
                imgEl.src = b64;
                imgEl.style.display = 'block';
            } else {
                imgEl.removeAttribute('src');
                // Ensure placeholder style is maintained if we want "black"
                // But user wants "picture placeholder reset to black". 
                // In CSS, background-color is black. So src="" implies showing background.
                // However, img tag without src might show border.

                // Better approach: uses a transparent pixel or empty src, let CSS bg show.
                // Or just clear src.

                // If CSS .live-feed has bg-color #000, then valid src covers it. 
                // Empty src might show broken image icon.
                // Let's set it to empty string.
            }
        }
    }

    // 2. Update Lists
    // Iterate over the known keys in the incoming payload OR update by DOM queries.
    // Iterating payload is cleaner for updates.
    if (state.statuses) {
        for (const [boltId, status] of Object.entries(state.statuses)) {
            const statusSpan = document.getElementById(`status-${boltId}`);
            if (statusSpan && statusSpan.textContent !== status) {
                statusSpan.textContent = status;
                // Update class
                statusSpan.className = 'item-status';
                if (status === 'OK') statusSpan.classList.add('ok');
                else if (status === 'NG') statusSpan.classList.add('ng');
                else statusSpan.classList.add('pending'); // Handles '-' or other states
            }
        }
    }

    // Update Section Headers based on current DOM state
    const sections = [
        { listId: 'list-right', headerKey: 'right' },
        { listId: 'list-upper', headerKey: 'upper' },
        { listId: 'list-left', headerKey: 'left' }
    ];

    sections.forEach(section => {
        const listEl = document.getElementById(section.listId);
        if (!listEl) return;

        const statusSpans = listEl.querySelectorAll('.item-status');
        const currentStatuses = Array.from(statusSpans).map(span => span.textContent);

        // Determine Section Status
        let sectionStatus = '-';
        if (currentStatuses.includes('NG')) {
            sectionStatus = 'NG';
        } else if (currentStatuses.length > 0 && currentStatuses.every(s => s === 'OK')) {
            sectionStatus = 'OK';
        }

        // Update Header
        const headerEl = elements.headers[section.headerKey];
        if (headerEl && headerEl.textContent !== sectionStatus) {
            headerEl.textContent = sectionStatus;
            headerEl.className = 'column-status';
            if (sectionStatus === 'OK') headerEl.classList.add('ok');
            else if (sectionStatus === 'NG') headerEl.classList.add('ng');
            else headerEl.classList.add('pending');
        }
    });

    // 3. Update Final Result
    // state.system.final_result
    const finalRes = state.system.final_result;
    elements.finalResult.textContent = finalRes;

    // Reset classes
    elements.finalResult.className = 'result-display';
    if (finalRes === 'OK') elements.finalResult.classList.add('ok');
    else if (finalRes === 'NG') elements.finalResult.classList.add('ng');
    else elements.finalResult.classList.add('pending'); // Handles '-' as default gray
}

function updateDateTime() {
    const now = new Date();
    const dateOptions = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
    elements.date.textContent = now.toLocaleDateString('en-GB', dateOptions);

    const timeOptions = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    elements.time.textContent = now.toLocaleTimeString('en-GB', timeOptions);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // initLists(); // Removed
    updateDateTime();
    setInterval(updateDateTime, 1000);
    connectWebSocket();
});
