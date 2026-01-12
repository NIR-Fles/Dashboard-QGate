// Mock Data Configuration
const boltData = {
    right: [
        { name: "BOLT_1", status: "OK" },
        { name: "BOLT_2", status: "OK" },
        { name: "BOLT_3", status: "OK" },
        { name: "BOLT_4", status: "OK" },
        { name: "BOLT_5", status: "OK" },
        { name: "BOLT_6", status: "OK" },
        { name: "BOLT_7", status: "OK" },
        { name: "BOLT_8", status: "OK" },
    ],
    upper: [
        { name: "BOLT_9", status: "OK" },
        { name: "BOLT_10", status: "OK" },
    ],
    left: [
        { name: "BOLT_11", status: "OK" },
        { name: "BOLT_12", status: "OK" },
        { name: "BOLT_13", status: "NG" },
        { name: "BOLT_14", status: "OK" },
        { name: "BOLT_15", status: "OK" },
        { name: "BOLT_16", status: "OK" },
        { name: "BOLT_17", status: "OK" },
        { name: "BOLT_18", status: "OK" },
        { name: "BOLT_19", status: "OK" },
        { name: "BOLT_20", status: "OK" },
    ],
};

function renderList(cameraKey, listId) {
    const listElement = document.getElementById(listId);
    if (!listElement) return;

    listElement.innerHTML = ''; // Clear current

    const items = boltData[cameraKey];
    items.forEach((item, index) => {
        const li = document.createElement('li');

        // Index
        const idxSpan = document.createElement('span');
        idxSpan.className = 'item-index';
        idxSpan.textContent = index + 1;

        // Name
        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = item.name;

        // Status Badge
        const statusSpan = document.createElement('span');
        statusSpan.className = `item-status ${item.status.toLowerCase()}`;
        statusSpan.textContent = item.status;

        li.appendChild(idxSpan);
        li.appendChild(nameSpan);
        li.appendChild(statusSpan);

        listElement.appendChild(li);
    });
}

function updateDateTime() {
    const now = new Date();

    // Date: "Thursday, 22 August 2024"
    const dateOptions = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
    const dateStr = now.toLocaleDateString('en-GB', dateOptions);

    // Time: "14:13:25"
    const timeOptions = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    const timeStr = now.toLocaleTimeString('en-GB', timeOptions);

    document.getElementById('date').textContent = dateStr;
    document.getElementById('time').textContent = timeStr;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    renderList('right', 'list-right');
    renderList('left', 'list-left');
    renderList('upper', 'list-upper');

    updateDateTime();
    setInterval(updateDateTime, 1000);
});
