const CONFIG = {
    cellSize: 20,
    colors: {
        unknown: '#2c2c2c',
        free: '#ffffff',
        wall: '#333333',
        obstacle: '#333333',
        target: '#03dac6',
        agent: '#cf6679',
        path: 'rgba(207, 102, 121, 0.3)',
        gridLine: '#333'
    }
};

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchPolicies();
});

async function fetchPolicies() {
    try {
        const response = await fetch('/api/policies');
        const data = await response.json();
        const policies = data.policies;

        // Populate Select
        const select = document.getElementById('policy');
        select.innerHTML = '';
        policies.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.textContent = p.toUpperCase().replace('_', ' ');
            select.appendChild(opt);
        });

        // Populate Checkboxes
        const checkboxContainer = document.getElementById('policy-checkboxes');
        checkboxContainer.innerHTML = '';
        policies.forEach((p, index) => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.cursor = 'pointer';

            // Format index with leading zero
            const idxStr = (index + 1).toString().padStart(2, '0');

            label.innerHTML = `<input type="checkbox" value="${p}" checked> [${idxStr}] ${p.toUpperCase().replace('_', ' ')}`;
            checkboxContainer.appendChild(label);
        });

    } catch (err) {
        console.error("Failed to fetch policies:", err);
    }
}

let simulationData = null;
let currentFrame = 0;
let isPlaying = false;
let playbackSpeed = 50;
let timerId = null;
let currentMode = 'single';

// DOM Elements
const canvasTruth = document.getElementById('ground-truth');
const ctxTruth = canvasTruth.getContext('2d');
const canvasBelief = document.getElementById('agent-belief');
const ctxBelief = canvasBelief.getContext('2d');

const runBtn = document.getElementById('run-btn');
const playBtn = document.getElementById('play-pause');
const timeline = document.getElementById('timeline');
const stepCounter = document.getElementById('step-counter');
const speedSlider = document.getElementById('speed-slider');

const tabBtns = document.querySelectorAll('.tab-btn');
const benchmarkControls = document.getElementById('benchmark-controls');
const runsContainer = document.getElementById('runs-container');
const historyContainer = document.getElementById('history-container');
const compareContainer = document.getElementById('compare-container');
const listTitle = document.getElementById('list-title').querySelector('span'); // Targeted
const policySelect = document.getElementById('policy');
const policyLabel = policySelect.previousElementSibling;
const policyCheckboxes = document.getElementById('policy-checkboxes');
const filterInput = document.getElementById('filter-input');
const historyFilter = document.getElementById('history-filter');

let cachedFolders = []; // Store folders for filtering

// Stats Elements
const statusVal = document.getElementById('status-val');
const stepsVal = document.getElementById('steps-val');
const targetsVal = document.getElementById('targets-val');
const successVal = document.getElementById('success-val');

// Event Listeners
runBtn.addEventListener('click', handleRun);
playBtn.addEventListener('click', togglePlay);
timeline.addEventListener('input', (e) => {
    pause();
    currentFrame = parseInt(e.target.value);
    renderFrame();
});

// Room Size Slider Listener
document.getElementById('room-size').addEventListener('input', (e) => {
    document.getElementById('room-size-val').textContent = e.target.value;
});

// Number of Rooms Slider Listener
document.getElementById('num-rooms').addEventListener('input', (e) => {
    document.getElementById('num-rooms-val').textContent = e.target.value;
});

// Complexity Slider Listener
document.getElementById('complexity').addEventListener('input', (e) => {
    document.getElementById('complexity-val').textContent = e.target.value + '%';
});

// Filter listener
filterInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    const filtered = cachedFolders.filter(f => f.name.toLowerCase().includes(term));
    renderHistoryList(filtered);
});

// Speed Slider Logic (Right = Faster => Lower delay)
// Max value 1000. Delay = 1000 - value + 10 (bias)
speedSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value);
    // Invert: High value = Low delay
    playbackSpeed = 1010 - val;

    // If playing, restart interval with new speed
    if (isPlaying) {
        pause();
        play();
    }
});

// Tab Switching
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;

        // UI State Management across tabs
        benchmarkControls.style.display = 'none';
        runsContainer.style.display = 'none';
        historyContainer.style.display = 'none';
        compareContainer.style.display = 'none';
        historyFilter.style.display = 'none';
        policyCheckboxes.style.display = 'none'; // Default hidden

        // Hide Telemetry Deck
        const deck = document.getElementById('telemetry-deck');
        if (deck) deck.style.display = 'none';

        // Default visibility
        policySelect.parentElement.style.display = 'block';
        policySelect.style.display = 'block'; // Ensure select is visible
        runBtn.style.display = 'block';

        listTitle.textContent = "Run Details";

        if (currentMode === 'benchmark') {
            benchmarkControls.style.display = 'block';
            runsContainer.style.display = 'block';
            listTitle.textContent = "Current Benchmark Runs";
            runsContainer.innerHTML = '';
        } else if (currentMode === 'history') {
            historyContainer.style.display = 'block';
            historyFilter.style.display = 'block'; // Show filter
            listTitle.textContent = "Saved Benchmarks";

            // Hide controls in history
            policySelect.parentElement.style.display = 'none';
            benchmarkControls.style.display = 'none';
            runBtn.style.display = 'none';

            fetchHistory();
        } else if (currentMode === 'compare') {
            benchmarkControls.style.display = 'block'; // recycle num runs input
            compareContainer.style.display = 'block';
            listTitle.textContent = "Comparison Results";

            // Show checkboxes, Hide select
            policySelect.style.display = 'none';
            policyCheckboxes.style.display = 'block';

        } else {
            // Single
            listTitle.textContent = "Single Run History";
            runsContainer.style.display = 'block';
            runsContainer.innerHTML = '';
        }
    });
});

async function handleRun() {
    if (currentMode === 'single') {
        runSingleSimulation();
    } else if (currentMode === 'benchmark') {
        runBenchmark();
    } else if (currentMode === 'compare') {
        runComparison();
    }
}

async function fetchHistory() {
    statusVal.textContent = "Fetching History...";
    try {
        const response = await fetch('/api/history');
        const data = await response.json();
        cachedFolders = data.folders; // Cache for filtering
        renderHistoryList(cachedFolders);
        statusVal.textContent = "Ready";
    } catch (err) {
        console.error(err);
        statusVal.textContent = "Error loading history";
    }
}

function renderHistoryList(folders) {
    historyContainer.innerHTML = '';
    if (folders.length === 0) {
        historyContainer.innerHTML = '<div style="color: #666; font-style: italic;">No saved benchmarks</div>';
        return;
    }

    folders.forEach(folder => {
        const div = document.createElement('div');
        div.className = 'run-item'; // Reuse styling
        div.style.borderLeftColor = '#bb86fc'; // Purple for folders
        div.innerHTML = `
            <div class="run-status">📁</div>
            <div>${folder.name}</div>
            <div class="run-info">${folder.count} runs</div>
        `;
        div.onclick = () => loadFolderRuns(folder.name);
        historyContainer.appendChild(div);
    });
}

async function loadFolderRuns(folderName) {
    statusVal.textContent = `Loading ${folderName}...`;
    showLoading("LOADING_DATA...");
    try {
        const response = await fetch(`/api/history/${folderName}`);
        const data = await response.json();

        // Switch view to show runs
        historyContainer.style.display = 'none';
        runsContainer.style.display = 'block';

        // Add Download Button
        const downloadBtnHtml = `<button onclick="window.location.href='/api/history/${folderName}/download'" style="width: auto; padding: 5px 10px; font-size: 0.8rem; margin-left: 10px; border: 1px solid var(--highlight); color: var(--highlight);">⬇ CSV</button>`;

        // Build metadata string if config exists
        let metaHtml = "";
        if (data.config) {
            const c = data.config;
            if (c.type === 'benchmark') {
                metaHtml = `<div style="font-size: 0.7rem; color: #888; margin-top: 5px;">MAP: ${c.width}x${c.height} (${c.map_type}) | RUNS: ${c.num_runs} | PL: ${c.policy}</div>`;
            } else if (c.type === 'compare') {
                metaHtml = `<div style="font-size: 0.7rem; color: #888; margin-top: 5px;">MAP: ${c.width}x${c.height} (${c.map_type}) | RUNS: ${c.num_runs} | PL: ${c.policies.length}</div>`;
            }
        }

        listTitle.innerHTML = `
            <div style="display:flex; align-items:center;">
                <span style="cursor:pointer; color: #bb86fc;" onclick="backToHistory()">⬅ LOGS</span> 
                <span style="margin: 0 10px;">/</span> 
                ${folderName} 
                ${downloadBtnHtml}
            </div>
            ${metaHtml}
        `;

        renderRunsList(data.runs);

        // Attempt to render charts if enough data implies comparison or benchmark
        const summary = summarizeRunsForCharts(data.runs);
        if (summary.length > 0) {
            renderCharts(summary);
            // Ensure charts are visible
            document.getElementById('charts-container').style.display = 'block';
        } else {
            document.getElementById('charts-container').style.display = 'none';
        }

        statusVal.textContent = "READY";
    } catch (err) {
        console.error(err);
        statusVal.textContent = "Error loading folder";
    } finally {
        hideLoading();
    }
}

function summarizeRunsForCharts(runs) {
    if (!runs || runs.length === 0) return [];

    // Group by policy
    const policies = {};
    runs.forEach(run => {
        const p = run.policy || 'unknown';
        if (!policies[p]) {
            policies[p] = { successCount: 0, steps: [], coverages: [], efficiencies: [], turns: [], collisions: [], runs: [] };
        }
        policies[p].runs.push(run);
        if (run.success) {
            policies[p].successCount++;
            policies[p].steps.push(run.steps);
        }
        if (run.coverage !== undefined) {
            policies[p].coverages.push(run.coverage);
        }
        if (run.efficiency !== undefined) policies[p].efficiencies.push(run.efficiency);
        if (run.turns !== undefined) policies[p].turns.push(run.turns);
        if (run.collisions !== undefined) policies[p].collisions.push(run.collisions);
    });

    // Valid policies only
    return Object.keys(policies).map(p => {
        const stats = policies[p];
        const total = stats.runs.length;
        const avgSteps = stats.steps.length ? (stats.steps.reduce((a, b) => a + b, 0) / stats.steps.length) : 0;

        // Coverage is avg of all runs usually
        const avgCov = stats.coverages.length ? (stats.coverages.reduce((a, b) => a + b, 0) / stats.coverages.length) : 0;
        const avgEff = stats.efficiencies && stats.efficiencies.length ? (stats.efficiencies.reduce((a, b) => a + b, 0) / stats.efficiencies.length) : 0;
        const avgTurns = stats.turns && stats.turns.length ? (stats.turns.reduce((a, b) => a + b, 0) / stats.turns.length) : 0;
        const avgColl = stats.collisions && stats.collisions.length ? (stats.collisions.reduce((a, b) => a + b, 0) / stats.collisions.length) : 0;

        return {
            policy: p,
            success_rate: (stats.successCount / total) * 100,
            avg_steps: parseFloat(avgSteps.toFixed(2)),
            avg_efficiency: parseFloat(avgEff.toFixed(3)),
            avg_turns: parseFloat(avgTurns.toFixed(2)),
            avg_collisions: parseFloat(avgColl.toFixed(2)),

            // Re-construct runs array structure expected by renderCharts logic
            // renderCharts logic calculates avg coverage from (run.coverage || 0)
            // So we just need to pass the runs back.
            runs: stats.runs
        };
    });
}

// Global scope for onclick
window.backToHistory = function () {
    historyContainer.style.display = 'block';
    runsContainer.style.display = 'none';
    listTitle.textContent = "SYSTEM_LOGS"; // Updated title to match new theme
}

async function runComparison() {
    const width = parseInt(document.getElementById('width').value);
    const height = parseInt(document.getElementById('height').value);
    const numRuns = parseInt(document.getElementById('num-runs').value);

    // New Params
    const mapType = document.getElementById('map-type').value;
    const complexity = parseInt(document.getElementById('complexity').value) / 100.0;
    const roomSize = parseInt(document.getElementById('room-size').value);
    const numRooms = parseInt(document.getElementById('num-rooms').value);

    // Gather selected policies
    const checkboxes = document.querySelectorAll('#policy-checkboxes input:checked');
    const selectedPolicies = Array.from(checkboxes).map(cb => cb.value);

    if (selectedPolicies.length === 0) {
        alert("Please select at least one policy to compare.");
        return;
    }

    statusVal.textContent = "Comparing...";
    runBtn.disabled = true;
    showLoading("INITIALIZING_COMPARISON...", 0);
    compareContainer.innerHTML = '';

    try {
        const response = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                width,
                height,
                num_runs: numRuns,
                policies: selectedPolicies,
                map_type: mapType,
                complexity,
                room_size: roomSize,
                map_num_rooms: numRooms
            })
        });

        const data = await response.json();
        const jobId = data.job_id;

        // Start Polling
        pollJob(jobId, (result) => {
            renderComparisonTable(result.summary);
            renderCharts(result.summary);
            statusVal.textContent = `Completed Comparison`;
            runBtn.disabled = false;
        });

    } catch (err) {
        statusVal.textContent = "Error";
        console.error(err);
        runBtn.disabled = false;
        hideLoading();
    }
}

// Global chart instances to destroy before re-rendering
let successChart = null;
let stepsChart = null;
let coverageChart = null;
let efficiencyChart = null;
let turnsChart = null;
let collisionsChart = null;

function renderCharts(summary) {
    // Reveal the main Telemetry Deck in main content, not sidebar
    const deck = document.getElementById('telemetry-deck');
    deck.style.display = 'block';

    // Ensure the charts container itself is visible
    document.getElementById('charts-container').style.display = 'block';

    // Auto-expand the deck if it's minimized, to show the new data
    if (!deck.classList.contains('expanded')) {
        deck.classList.add('expanded');
        const icon = document.getElementById('deck-toggle-icon');
        if (icon) icon.textContent = "▼ MINIMIZE";
    }

    const labels = summary.map(s => s.policy);
    const successData = summary.map(s => s.success_rate);
    const stepsData = summary.map(s => s.avg_steps);

    // Calculate avg coverage from runs
    const coverageData = summary.map(s => {
        const runs = s.runs;
        if (runs.length === 0) return 0;
        const total = runs.reduce((acc, r) => acc + (r.coverage || 0), 0);
        return (total / runs.length).toFixed(1);
    });

    const efficiencyData = summary.map(s => s.avg_efficiency);
    const turnsData = summary.map(s => s.avg_turns);
    const collisionsData = summary.map(s => s.avg_collisions);

    const commonOptions = {
        responsive: true,
        plugins: {
            legend: {
                labels: { color: '#00ff41', font: { family: 'Courier Prime' } }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: '#333' },
                ticks: { color: '#00ff41', font: { family: 'Courier Prime' } }
            },
            x: {
                grid: { color: '#333' },
                ticks: { color: '#00ff41', font: { family: 'Courier Prime' } }
            }
        }
    };

    // 1. Success Chart
    if (successChart) successChart.destroy();
    successChart = new Chart(document.getElementById('successChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Success Rate (%)',
                data: successData,
                backgroundColor: 'rgba(0, 255, 65, 0.2)', // Neon green fills
                borderColor: '#00ff41',
                borderWidth: 1
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 100 } } }
    });

    // 2. Steps Chart
    if (stepsChart) stepsChart.destroy();
    stepsChart = new Chart(document.getElementById('stepsChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Steps (Lower is Better)',
                data: stepsData,
                backgroundColor: 'rgba(0, 176, 255, 0.2)', // Neon Cyan
                borderColor: '#00b0ff',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });

    // 3. Coverage Chart
    if (coverageChart) coverageChart.destroy();
    coverageChart = new Chart(document.getElementById('coverageChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Coverage (%)',
                data: coverageData,
                backgroundColor: 'rgba(255, 0, 85, 0.2)', // Neon Red/Pink
                borderColor: '#ff0055',
                borderWidth: 1
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 100 } } }
    });


    // 4. Efficiency Chart
    if (efficiencyChart) efficiencyChart.destroy();
    efficiencyChart = new Chart(document.getElementById('efficiencyChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Search Efficiency (0-1)',
                data: efficiencyData,
                backgroundColor: 'rgba(255, 193, 7, 0.2)', // Amber
                borderColor: '#ffc107',
                borderWidth: 1
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 1.0 } } }
    });

    // 5. Turns Chart
    if (turnsChart) turnsChart.destroy();
    turnsChart = new Chart(document.getElementById('turnsChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Turns',
                data: turnsData,
                backgroundColor: 'rgba(156, 39, 176, 0.2)', // Purple
                borderColor: '#9c27b0',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });

    // 6. Collisions Chart
    if (collisionsChart) collisionsChart.destroy();
    collisionsChart = new Chart(document.getElementById('collisionsChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Collisions',
                data: collisionsData,
                backgroundColor: 'rgba(244, 67, 54, 0.2)', // Red
                borderColor: '#f44336',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });
}

function renderComparisonTable(summary) {
    let html = '<table style="width:100%; border-collapse: collapse; margin-bottom: 20px;">';
    html += '<tr style="border-bottom: 1px solid #444; color: #a0a0a0;"><th style="text-align:left; padding:5px;">Policy</th><th style="padding:5px;">Success %</th><th style="padding:5px;">Avg Steps</th><th style="padding:5px;">Eff</th><th style="padding:5px;">Turns</th><th style="padding:5px;">Coll</th></tr>';

    summary.forEach(item => {
        html += `
            <tr style="border-bottom: 1px solid #333;">
                <td style="padding:8px; font-weight:bold; color: #bb86fc;">${item.policy}</td>
                <td style="padding:8px; text-align:center;">${item.success_rate.toFixed(1)}%</td>
                <td style="padding:8px; text-align:center;">${item.avg_steps}</td>
                <td style="padding:8px; text-align:center;">${item.avg_efficiency}</td>
                <td style="padding:8px; text-align:center;">${item.avg_turns}</td>
                <td style="padding:8px; text-align:center;">${item.avg_collisions}</td>
            </tr>
        `;
    });
    html += '</table>';

    // Detailed runs
    summary.forEach(item => {
        html += `<div style="font-size:0.8rem; color:#a0a0a0; margin-top:10px;">${item.policy} Details</div>`;
        item.runs.forEach((run, idx) => {
            html += `
                <div class="run-item ${run.success ? 'success' : 'fail'}" onclick="loadSimulationByID('${run.id}', this)">
                    <div class="run-status">${run.success ? '✅' : '❌'}</div>
                    <div>Seed: ${run.seed}</div>
                    <div class="run-info">Steps: ${run.steps}</div>
                </div>
            `;
        });
    });

    compareContainer.innerHTML = html;
}

// Constraint Logic
function updateRoomConstraints() {
    const w = parseInt(document.getElementById('width').value) || 20;
    const h = parseInt(document.getElementById('height').value) || 20;
    const roomSize = parseInt(document.getElementById('room-size').value) || 5;

    // Estimate max rooms
    const totalArea = w * h;
    // Room takes (size+2)^2 area including walls approx
    const roomArea = Math.pow(roomSize + 2, 2);

    // Packing efficiency 0.6
    const maxRooms = Math.floor((totalArea * 0.6) / roomArea);
    // Hard cap 100
    const safeMax = Math.min(100, Math.max(1, maxRooms));

    const numRoomsSlider = document.getElementById('num-rooms');
    const currentVal = parseInt(numRoomsSlider.value);

    // Update Slider Attributes
    numRoomsSlider.max = safeMax;

    // Clamp value
    if (currentVal > safeMax) {
        numRoomsSlider.value = safeMax;
        document.getElementById('num-rooms-val').textContent = safeMax;
    }
}

// Add listeners for constraints
['width', 'height', 'room-size'].forEach(id => {
    document.getElementById(id).addEventListener('input', updateRoomConstraints);
});
// Call initially
updateRoomConstraints();

async function runSingleSimulation() {
    const width = parseInt(document.getElementById('width').value);
    const height = parseInt(document.getElementById('height').value);
    const policy = document.getElementById('policy').value;
    const mapType = document.getElementById('map-type').value;
    const complexity = parseInt(document.getElementById('complexity').value) / 100.0;
    const roomSize = parseInt(document.getElementById('room-size').value);
    const numRooms = parseInt(document.getElementById('num-rooms').value);

    statusVal.textContent = "Running...";
    runBtn.disabled = true;

    try {
        const response = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ width, height, policy, map_type: mapType, complexity, room_size: roomSize, map_num_rooms: numRooms })
        });

        const data = await response.json();
        loadSimulationData(data);

        statusVal.textContent = "Finished";
    } catch (err) {
        statusVal.textContent = "Error";
        console.error(err);
    } finally {
        runBtn.disabled = false;
    }
}

async function runBenchmark() {
    const width = parseInt(document.getElementById('width').value);
    const height = parseInt(document.getElementById('height').value);
    const policy = document.getElementById('policy').value;
    const numRuns = parseInt(document.getElementById('num-runs').value);
    const mapType = document.getElementById('map-type').value;
    const complexity = parseInt(document.getElementById('complexity').value) / 100.0;
    const roomSize = parseInt(document.getElementById('room-size').value);
    const numRooms = parseInt(document.getElementById('num-rooms').value);

    statusVal.textContent = "Benchmarking...";
    runBtn.disabled = true;
    showLoading("INITIALIZING_BENCHMARK...", 0);
    runsContainer.innerHTML = ''; // Clear list

    try {
        const response = await fetch('/api/benchmark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ width, height, policy, num_runs: numRuns, map_type: mapType, complexity, room_size: roomSize, map_num_rooms: numRooms })
        });

        const data = await response.json();
        const jobId = data.job_id;

        // Poll
        pollJob(jobId, (result) => {
            renderRunsList(result.runs);
            statusVal.textContent = `Completed ${result.runs.length} runs`;
            runBtn.disabled = false;
        });

    } catch (err) {
        statusVal.textContent = "Error";
        console.error(err);
        hideLoading();
        runBtn.disabled = false;
    }
}

function renderRunsList(runs) {
    runsContainer.innerHTML = '';
    runs.forEach((run, index) => {
        const div = document.createElement('div');
        div.className = `run-item ${run.success ? 'success' : 'fail'}`;

        let runLabel = `Run #${index + 1}`;
        if (run.policy) {
            runLabel = `<span style="text-transform: capitalize; font-weight: bold;">${run.policy}</span>`;
        }

        div.innerHTML = `
            <div class="run-status">${run.success ? '✅' : '❌'}</div>
            <div>${runLabel}</div>
            <div class="run-info">Steps: ${run.steps} | Seed: ${run.seed}</div>
        `;
        div.onclick = () => loadSimulationByID(run.id, div);
        runsContainer.appendChild(div);
    });
}

async function loadSimulationByID(id, element) {
    // UI selection
    document.querySelectorAll('.run-item').forEach(el => el.classList.remove('active'));
    if (element) element.classList.add('active');

    statusVal.textContent = "Loading...";
    try {
        const response = await fetch(`/api/simulation/${id}`);
        const data = await response.json();
        loadSimulationData(data);
        statusVal.textContent = "Loaded Run";
    } catch (err) {
        console.error(err);
        statusVal.textContent = "Load Failed";
    }
}

function loadSimulationData(data) {
    simulationData = data;

    setupCanvas(data.config.width, data.config.height);
    timeline.max = simulationData.history.length - 1;
    timeline.value = 0;
    currentFrame = 0;

    updateStats();
    renderFrame();

    // Auto play on load
    play();
}

function updateStats() {
    if (!simulationData) return;

    const stats = simulationData.stats;
    stepsVal.textContent = stats.steps;
    targetsVal.textContent = `${stats.targets_found} / ${stats.targets_total}`;
    successVal.textContent = stats.success ? "YES" : "NO";
}

function setupCanvas(w, h) {
    const pxW = w * CONFIG.cellSize;
    const pxH = h * CONFIG.cellSize;

    canvasTruth.width = pxW;
    canvasTruth.height = pxH;
    canvasBelief.width = pxW;
    canvasBelief.height = pxH;
}

function renderFrame() {
    if (!simulationData) return;

    const state = simulationData.history[currentFrame];
    const map = simulationData.map;

    renderGroundTruth(state, map);
    renderBeliefMap(state, map);

    timeline.value = currentFrame;
    stepCounter.textContent = `${currentFrame} / ${simulationData.history.length - 1}`;
}

function renderGrid(ctx, w, h) {
    ctx.strokeStyle = CONFIG.colors.gridLine;
    ctx.lineWidth = 1;

    for (let x = 0; x <= w; x++) {
        ctx.beginPath();
        ctx.moveTo(x * CONFIG.cellSize, 0);
        ctx.lineTo(x * CONFIG.cellSize, h * CONFIG.cellSize);
        ctx.stroke();
    }

    for (let y = 0; y <= h; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * CONFIG.cellSize);
        ctx.lineTo(w * CONFIG.cellSize, y * CONFIG.cellSize);
        ctx.stroke();
    }
}

function renderGroundTruth(state, map) {
    const w = map.width;
    const h = map.height;

    ctxTruth.fillStyle = CONFIG.colors.free;
    ctxTruth.fillRect(0, 0, canvasTruth.width, canvasTruth.height);

    ctxTruth.fillStyle = CONFIG.colors.wall;
    for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
            if (map.grid[y][x] === 1) {
                ctxTruth.fillRect(x * CONFIG.cellSize, y * CONFIG.cellSize, CONFIG.cellSize, CONFIG.cellSize);
            }
        }
    }

    ctxTruth.fillStyle = CONFIG.colors.target;
    for (const [tx, ty] of map.targets) {
        ctxTruth.beginPath();
        ctxTruth.arc(
            tx * CONFIG.cellSize + CONFIG.cellSize / 2,
            ty * CONFIG.cellSize + CONFIG.cellSize / 2,
            CONFIG.cellSize / 3, 0, Math.PI * 2
        );
        ctxTruth.fill();
    }

    drawAgent(ctxTruth, state.x, state.y);
    renderGrid(ctxTruth, w, h);
}

function renderBeliefMap(state, map) {
    const w = map.width;
    const h = map.height;
    const belief = state.belief_map;

    ctxBelief.fillStyle = CONFIG.colors.unknown;
    ctxBelief.fillRect(0, 0, canvasBelief.width, canvasBelief.height);

    for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
            const cell = belief[y][x];
            if (cell === 0) {
                ctxBelief.fillStyle = CONFIG.colors.free;
                ctxBelief.fillRect(x * CONFIG.cellSize, y * CONFIG.cellSize, CONFIG.cellSize, CONFIG.cellSize);
            } else if (cell === 1) {
                ctxBelief.fillStyle = CONFIG.colors.wall;
                ctxBelief.fillRect(x * CONFIG.cellSize, y * CONFIG.cellSize, CONFIG.cellSize, CONFIG.cellSize);
            }
        }
    }

    ctxBelief.fillStyle = CONFIG.colors.target;
    for (const [tx, ty] of state.found_targets) {
        ctxBelief.beginPath();
        ctxBelief.arc(
            tx * CONFIG.cellSize + CONFIG.cellSize / 2,
            ty * CONFIG.cellSize + CONFIG.cellSize / 2,
            CONFIG.cellSize / 3, 0, Math.PI * 2
        );
        ctxBelief.fill();
    }

    drawAgent(ctxBelief, state.x, state.y);
    renderGrid(ctxBelief, w, h);
}

function drawAgent(ctx, x, y) {
    ctx.fillStyle = CONFIG.colors.agent;
    ctx.beginPath();
    ctx.arc(
        x * CONFIG.cellSize + CONFIG.cellSize / 2,
        y * CONFIG.cellSize + CONFIG.cellSize / 2,
        CONFIG.cellSize / 2.5, 0, Math.PI * 2
    );
    ctx.fill();
}

function togglePlay() {
    if (isPlaying) {
        pause();
    } else {
        play();
    }
}

function play() {
    if (!simulationData) return;
    isPlaying = true;
    playBtn.textContent = '⏸';

    clearInterval(timerId); // Clear any existing

    timerId = setInterval(() => {
        if (currentFrame < simulationData.history.length - 1) {
            currentFrame++;
            renderFrame();
        } else {
            pause();
        }
    }, playbackSpeed);
}

function pause() {
    isPlaying = false;
    playBtn.textContent = '▶';
    if (timerId) clearInterval(timerId);
}

// Telemetry Deck Toggle
function toggleDeck() {
    const deck = document.getElementById('telemetry-deck');
    const icon = document.getElementById('deck-toggle-icon');

    deck.classList.toggle('expanded');

    if (deck.classList.contains('expanded')) {
        icon.textContent = "▼ MINIMIZE";
    } else {
        icon.textContent = "▲ MAXIMIZE";
    }
}

// Loading UI Logic with Progress
function showLoading(msg = "SYSTEM_PROCESSING...", progress = 0) {
    document.querySelector('.loading-text').textContent = msg;
    document.getElementById('loading-overlay').style.display = 'flex';
    updateProgressBar(progress);
}

function updateProgressBar(percent) {
    const fill = document.querySelector('.progress-fill');
    // For filling effect, we set width
    fill.style.width = `${percent}%`;
    fill.style.animation = 'none'; // Disable scan animation for real progress
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
    // Reset
    const fill = document.querySelector('.progress-fill');
    fill.style.width = '50%';
    fill.style.animation = 'loadbar 2s ease-in-out infinite';
}

async function pollJob(jobId, onSuccess) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/job/${jobId}`);
            const job = await res.json();

            if (job.error) {
                clearInterval(interval);
                hideLoading();
                alert(`Job Failed: ${job.error}`);
                return;
            }

            // Calc percentage
            const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
            updateProgressBar(pct);
            document.querySelector('.loading-text').textContent = `PROCESSING... ${pct}%`;

            if (job.status === 'completed') {
                clearInterval(interval);
                // Slight delay to show 100%
                setTimeout(() => {
                    hideLoading();
                    onSuccess(job.result);
                }, 500);
            }
        } catch (err) {
            console.error(err);
            clearInterval(interval);
            hideLoading();
        }
    }, 500); // Poll every 500ms
}
