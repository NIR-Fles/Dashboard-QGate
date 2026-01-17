// Backend WebSocket URL
// Automatically determine host based on where the page is served from
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.host; // e.g., "localhost:8000" or "192.168.1.50:8000"
const WS_URL = `${protocol}//${host}/ws`;

// Static Bolt Configuration (Restored)
const boltData = {
    right: [
        "BOLT_1", "BOLT_2", "BOLT_3", "BOLT_4",
        "BOLT_5", "BOLT_6", "BOLT_7", "BOLT_8"
    ],
    upper: [
        "BOLT_9", "BOLT_10"
    ],
    left: [
        "BOLT_11", "BOLT_12", "BOLT_13", "BOLT_14",
        "BOLT_15", "BOLT_16", "BOLT_17", "BOLT_18",
        "BOLT_19", "BOLT_20"
    ]
};

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
    }
};

// Initialize Lists immediately
function initLists() {
    for (const [camKey, bolts] of Object.entries(boltData)) {
        const listEl = elements.lists[camKey];
        if (!listEl) continue;

        listEl.innerHTML = '';
        bolts.forEach((boltId, index) => {
            const li = document.createElement('li');

            // Index
            const idxSpan = document.createElement('span');
            idxSpan.className = 'item-index';
            idxSpan.textContent = index + 1;

            // Name
            const nameSpan = document.createElement('span');
            nameSpan.className = 'item-name';
            nameSpan.textContent = boltId;

            // Status Badge (Default Pending)
            const statusSpan = document.createElement('span');
            statusSpan.className = 'item-status pending';
            statusSpan.textContent = '-';

            li.appendChild(idxSpan);
            li.appendChild(nameSpan);
            li.appendChild(statusSpan);

            listEl.appendChild(li);
        });
    }
}

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
    // Use the static keys to match the lists
    for (const [camKey, bolts] of Object.entries(boltData)) {
        const listEl = elements.lists[camKey];
        if (!listEl) continue;

        const listItems = listEl.children;

        bolts.forEach((boltId, index) => {
            // Get status from backend state, default to "-"
            const status = state.statuses[boltId] || "-";

            const li = listItems[index];
            if (li) {
                const statusSpan = li.querySelector('.item-status');
                if (statusSpan) {
                    // Update only if changed
                    if (statusSpan.textContent !== status) {
                        statusSpan.textContent = status;

                        // Update class
                        statusSpan.className = 'item-status';
                        if (status === 'OK') statusSpan.classList.add('ok');
                        else if (status === 'NG') statusSpan.classList.add('ng');
                        else statusSpan.classList.add('pending');
                    }
                }
            }
        });
    }

    // 3. Update Final Result
    // state.system.final_result
    const finalRes = state.system.final_result;
    elements.finalResult.textContent = finalRes;

    // Reset classes
    elements.finalResult.className = 'result-display';
    if (finalRes === 'OK') elements.finalResult.classList.add('ok');
    else if (finalRes === 'NG') elements.finalResult.classList.add('ng');
    else elements.finalResult.classList.add('pending');
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
    initLists(); // Render static list immediately
    updateDateTime();
    setInterval(updateDateTime, 1000);
    connectWebSocket();
});
