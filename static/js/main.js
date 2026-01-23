const CONFIG = {
    cellSize: 6,
    colors: {
        unknown: '#2c2c2c',
        free: '#ffffff',
        wall: '#333333',
        obstacle: '#333333',
        target: '#ff4444', // Red for targets
        baseStation: '#00ff88', // Green for base station
        agent: '#cf6679',
        path: 'rgba(207, 102, 121, 0.3)',
        gridLine: '#333'
    },
    // Distinct colors for multiple drones
    droneColors: [
        '#cf6679', // Pink (original)
        '#bb86fc', // Purple
        '#03dac6', // Teal (target-like but darker)
        '#ff7043', // Orange
        '#42a5f5', // Blue
        '#66bb6a', // Green
        '#ffca28', // Amber
        '#ec407a', // Pink variant
        '#7e57c2', // Deep purple
        '#26c6da'  // Cyan
    ]
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
let aggregatedStatsData = null; // Store aggregated stats to preserve them

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

// Number of Drones Slider Listener
document.getElementById('num-drones').addEventListener('input', (e) => {
    document.getElementById('num-drones-val').textContent = e.target.value;
});

// Number of Targets Slider Listener
document.getElementById('num-targets').addEventListener('input', (e) => {
    document.getElementById('num-targets-val').textContent = e.target.value;
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
            aggregatedStatsData = null; // Clear aggregated stats in single mode
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
        // Sort folders by name in descending order (latest first)
        cachedFolders = data.folders.sort((a, b) => b.name.localeCompare(a.name));
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
            // Show aggregated stats from summary
            displayAggregatedStatsFromSummary(summary);
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
            policies[p] = { 
                successCount: 0, 
                steps: [], 
                coverages: [], 
                efficiencies: [], 
                turns: [], 
                collisions: [], 
                total_distance: [],
                avg_distance_per_agent: [],
                total_idle_steps: [],
                avg_idle_steps_per_agent: [],
                total_backtracking: [],
                avg_backtracking_per_agent: [],
                avg_frontier_size: [],
                max_frontier_size: [],
                avg_exploration_rate: [],
                avg_network_partitions: [],
                max_network_partitions: [],
                communication_connectivity: [],
                runs: [] 
            };
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
        
        // New metrics
        if (run.total_distance_traveled !== undefined) policies[p].total_distance.push(run.total_distance_traveled);
        if (run.avg_distance_per_agent !== undefined) policies[p].avg_distance_per_agent.push(run.avg_distance_per_agent);
        if (run.total_idle_steps !== undefined) policies[p].total_idle_steps.push(run.total_idle_steps);
        if (run.avg_idle_steps_per_agent !== undefined) policies[p].avg_idle_steps_per_agent.push(run.avg_idle_steps_per_agent);
        if (run.total_backtracking !== undefined) policies[p].total_backtracking.push(run.total_backtracking);
        if (run.avg_backtracking_per_agent !== undefined) policies[p].avg_backtracking_per_agent.push(run.avg_backtracking_per_agent);
        if (run.avg_frontier_size !== undefined) policies[p].avg_frontier_size.push(run.avg_frontier_size);
        if (run.max_frontier_size !== undefined) policies[p].max_frontier_size.push(run.max_frontier_size);
        if (run.avg_exploration_rate !== undefined) policies[p].avg_exploration_rate.push(run.avg_exploration_rate);
        if (run.avg_network_partitions !== undefined) policies[p].avg_network_partitions.push(run.avg_network_partitions);
        if (run.max_network_partitions !== undefined) policies[p].max_network_partitions.push(run.max_network_partitions);
        if (run.communication_connectivity !== undefined) policies[p].communication_connectivity.push(run.communication_connectivity);
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

        // New metrics averages
        const avgDistance = stats.total_distance.length ? (stats.total_distance.reduce((a, b) => a + b, 0) / stats.total_distance.length) : 0;
        const avgDistPerAgent = stats.avg_distance_per_agent.length ? (stats.avg_distance_per_agent.reduce((a, b) => a + b, 0) / stats.avg_distance_per_agent.length) : 0;
        const avgIdleSteps = stats.total_idle_steps.length ? (stats.total_idle_steps.reduce((a, b) => a + b, 0) / stats.total_idle_steps.length) : 0;
        const avgIdlePerAgent = stats.avg_idle_steps_per_agent.length ? (stats.avg_idle_steps_per_agent.reduce((a, b) => a + b, 0) / stats.avg_idle_steps_per_agent.length) : 0;
        const avgBacktracking = stats.total_backtracking.length ? (stats.total_backtracking.reduce((a, b) => a + b, 0) / stats.total_backtracking.length) : 0;
        const avgBacktrackPerAgent = stats.avg_backtracking_per_agent.length ? (stats.avg_backtracking_per_agent.reduce((a, b) => a + b, 0) / stats.avg_backtracking_per_agent.length) : 0;
        const avgFrontier = stats.avg_frontier_size.length ? (stats.avg_frontier_size.reduce((a, b) => a + b, 0) / stats.avg_frontier_size.length) : 0;
        const maxFrontier = stats.max_frontier_size.length ? Math.max(...stats.max_frontier_size) : 0;
        const avgExploration = stats.avg_exploration_rate.length ? (stats.avg_exploration_rate.reduce((a, b) => a + b, 0) / stats.avg_exploration_rate.length) : 0;
        const avgPartitions = stats.avg_network_partitions.length ? (stats.avg_network_partitions.reduce((a, b) => a + b, 0) / stats.avg_network_partitions.length) : 0;
        const maxPartitions = stats.max_network_partitions.length ? Math.max(...stats.max_network_partitions) : 0;
        const avgConnectivity = stats.communication_connectivity.length ? (stats.communication_connectivity.reduce((a, b) => a + b, 0) / stats.communication_connectivity.length) : 0;

        return {
            policy: p,
            success_rate: (stats.successCount / total) * 100,
            avg_steps: parseFloat(avgSteps.toFixed(2)),
            avg_efficiency: parseFloat(avgEff.toFixed(3)),
            avg_turns: parseFloat(avgTurns.toFixed(2)),
            avg_collisions: parseFloat(avgColl.toFixed(2)),
            avg_distance_traveled: parseFloat(avgDistance.toFixed(1)),
            avg_distance_per_agent: parseFloat(avgDistPerAgent.toFixed(1)),
            avg_idle_steps: parseFloat(avgIdleSteps.toFixed(1)),
            avg_idle_steps_per_agent: parseFloat(avgIdlePerAgent.toFixed(1)),
            avg_backtracking: parseFloat(avgBacktracking.toFixed(1)),
            avg_backtracking_per_agent: parseFloat(avgBacktrackPerAgent.toFixed(1)),
            avg_frontier_size: parseFloat(avgFrontier.toFixed(1)),
            max_frontier_size: maxFrontier,
            avg_exploration_rate: parseFloat(avgExploration.toFixed(3)),
            avg_network_partitions: parseFloat(avgPartitions.toFixed(1)),
            max_network_partitions: maxPartitions,
            avg_communication_connectivity: parseFloat(avgConnectivity.toFixed(3)),

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

    // Params
    const complexity = parseInt(document.getElementById('complexity').value) / 100.0;
    const roomSize = parseInt(document.getElementById('room-size').value);
    const numRooms = parseInt(document.getElementById('num-rooms').value);
    const numDrones = parseInt(document.getElementById('num-drones').value);
    const numTargets = parseInt(document.getElementById('num-targets').value);

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
                map_type: 'floorplan',
                complexity,
                room_size: roomSize,
                map_num_rooms: numRooms,
                num_drones: numDrones,
                num_targets: numTargets
            })
        });

        const data = await response.json();
        const jobId = data.job_id;

        // Start Polling
        pollJob(jobId, (result) => {
            renderComparisonTable(result.summary);
            renderCharts(result.summary);
            // Show aggregated stats from comparison
            displayAggregatedStatsFromSummary(result.summary);
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
let distanceChart = null;
let idleStepsChart = null;
let backtrackingChart = null;
let frontierChart = null;
let explorationChart = null;
let connectivityChart = null;

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

    // New metrics data
    const distanceData = summary.map(s => s.avg_distance_traveled);
    const idleStepsData = summary.map(s => s.avg_idle_steps);
    const backtrackingData = summary.map(s => s.avg_backtracking);
    const frontierData = summary.map(s => s.avg_frontier_size);
    const explorationData = summary.map(s => s.avg_exploration_rate * 100); // Convert to percentage
    const connectivityData = summary.map(s => s.avg_communication_connectivity * 100); // Convert to percentage

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

    // 7. Distance Chart
    if (distanceChart) distanceChart.destroy();
    distanceChart = new Chart(document.getElementById('distanceChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Distance Traveled',
                data: distanceData,
                backgroundColor: 'rgba(76, 175, 80, 0.2)', // Green
                borderColor: '#4caf50',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });

    // 8. Idle Steps Chart
    if (idleStepsChart) idleStepsChart.destroy();
    idleStepsChart = new Chart(document.getElementById('idleStepsChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Idle Steps (Lower is Better)',
                data: idleStepsData,
                backgroundColor: 'rgba(255, 152, 0, 0.2)', // Orange
                borderColor: '#ff9800',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });

    // 9. Backtracking Chart
    if (backtrackingChart) backtrackingChart.destroy();
    backtrackingChart = new Chart(document.getElementById('backtrackingChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Backtracking (Lower is Better)',
                data: backtrackingData,
                backgroundColor: 'rgba(156, 39, 176, 0.2)', // Purple
                borderColor: '#9c27b0',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });

    // 10. Frontier Chart
    if (frontierChart) frontierChart.destroy();
    frontierChart = new Chart(document.getElementById('frontierChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Frontier Size',
                data: frontierData,
                backgroundColor: 'rgba(0, 188, 212, 0.2)', // Cyan
                borderColor: '#00bcd4',
                borderWidth: 1
            }]
        },
        options: commonOptions
    });

    // 11. Exploration Chart
    if (explorationChart) explorationChart.destroy();
    explorationChart = new Chart(document.getElementById('explorationChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Exploration Rate (%)',
                data: explorationData,
                backgroundColor: 'rgba(255, 235, 59, 0.2)', // Yellow
                borderColor: '#ffeb3b',
                borderWidth: 1
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 100 } } }
    });

    // 12. Connectivity Chart
    if (connectivityChart) connectivityChart.destroy();
    connectivityChart = new Chart(document.getElementById('connectivityChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Connectivity (%)',
                data: connectivityData,
                backgroundColor: 'rgba(255, 87, 34, 0.2)', // Deep Orange
                borderColor: '#ff5722',
                borderWidth: 1
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 100 } } }
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
    const w = parseInt(document.getElementById('width').value) || 100;
    const h = parseInt(document.getElementById('height').value) || 100;
    const roomSize = parseInt(document.getElementById('room-size').value) || 15;

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
    const complexity = parseInt(document.getElementById('complexity').value) / 100.0;
    const roomSize = parseInt(document.getElementById('room-size').value);
    const numRooms = parseInt(document.getElementById('num-rooms').value);
    const numDrones = parseInt(document.getElementById('num-drones').value);
    const numTargets = parseInt(document.getElementById('num-targets').value);

    statusVal.textContent = "Running...";
    runBtn.disabled = true;

    try {
        const response = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                width,
                height,
                policy,
                map_type: 'floorplan',
                complexity,
                room_size: roomSize,
                map_num_rooms: numRooms,
                num_drones: numDrones,
                num_targets: numTargets
            })
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
    const complexity = parseInt(document.getElementById('complexity').value) / 100.0;
    const roomSize = parseInt(document.getElementById('room-size').value);
    const numRooms = parseInt(document.getElementById('num-rooms').value);
    const numDrones = parseInt(document.getElementById('num-drones').value);
    const numTargets = parseInt(document.getElementById('num-targets').value);

    statusVal.textContent = "Benchmarking...";
    runBtn.disabled = true;
    showLoading("INITIALIZING_BENCHMARK...", 0);
    runsContainer.innerHTML = ''; // Clear list

    try {
        const response = await fetch('/api/benchmark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                width,
                height,
                policy,
                num_runs: numRuns,
                map_type: 'floorplan',
                complexity,
                room_size: roomSize,
                map_num_rooms: numRooms,
                num_drones: numDrones,
                num_targets: numTargets
            })
        });

        const data = await response.json();
        const jobId = data.job_id;

        // Poll
        pollJob(jobId, (result) => {
            console.log("Benchmark completed, result:", result);
            renderRunsList(result.runs);
            // Show aggregated stats
            displayAggregatedStats(result.runs);
            // Show telemetry deck for aggregated stats
            const deck = document.getElementById('telemetry-deck');
            console.log("Telemetry deck element:", deck);
            if (deck) {
                deck.style.display = 'block';
                // Auto-expand the deck to show the new data
                if (!deck.classList.contains('expanded')) {
                    deck.classList.add('expanded');
                    const icon = document.getElementById('deck-toggle-icon');
                    if (icon) icon.textContent = "▼ MINIMIZE";
                }
            }
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

    // Uncompress history if needed (delta encoded)
    if (data.history.length > 0 && !data.history[0].belief_map && data.history[0].belief_diff) {
        reconstructHistory(data);
    }

    setupCanvas(data.config.width, data.config.height);
    timeline.max = simulationData.history.length - 1;
    timeline.value = 0;
    currentFrame = 0;

    // Only update individual run stats in single mode
    if (currentMode === 'single') {
        updateStats();
    }
    renderFrame();

    // Auto play on load
    play();
}

function reconstructHistory(data) {
    // Use map dimensions for consistency with rendering if available
    const w = parseInt(data.map ? data.map.width : data.config.width);
    const h = parseInt(data.map ? data.map.height : data.config.height);

    // Initialize current map with -1 (unknown)
    let currentMap = [];
    for (let y = 0; y < h; y++) {
        let row = [];
        for (let x = 0; x < w; x++) row.push(-1);
        currentMap.push(row);
    }

    // Iterate through history and apply diffs
    data.history.forEach(state => {
        if (state.belief_diff) {
            state.belief_diff.forEach(change => {
                const r = change[0];
                const c = change[1];
                const val = change[2];
                // r is row (y), c is col (x)
                if (r >= 0 && r < h && c >= 0 && c < w) {
                    currentMap[r][c] = val;
                }
            });
        }
        // Save snapshot of full map for rendering
        // Use map/slice for faster copy than JSON.parse/stringify
        state.belief_map = currentMap.map(row => row.slice());
    });
}

function updateStats() {
    if (!simulationData) return;

    // Always show aggregated stats if available (benchmark, compare, history)
    if (aggregatedStatsData) {
        displayStoredAggregatedStats();
        return;
    }

    // Otherwise show single run stats
    const stats = simulationData.stats;
    stepsVal.textContent = stats.steps;
    targetsVal.textContent = `${stats.targets_found} / ${stats.targets_total}`;
    successVal.textContent = stats.success ? "YES" : "NO";

    // New metrics
    document.getElementById('distance-val').textContent = stats.total_distance_traveled ? stats.total_distance_traveled.toFixed(1) : '0.0';
    document.getElementById('avg-distance-val').textContent = stats.avg_distance_per_agent ? stats.avg_distance_per_agent.toFixed(1) : '0.0';
    document.getElementById('idle-steps-val').textContent = stats.total_idle_steps || 0;
    document.getElementById('avg-idle-val').textContent = stats.avg_idle_steps_per_agent ? stats.avg_idle_steps_per_agent.toFixed(1) : '0.0';
    document.getElementById('backtracking-val').textContent = stats.total_backtracking || 0;
    document.getElementById('avg-backtrack-val').textContent = stats.avg_backtracking_per_agent ? stats.avg_backtracking_per_agent.toFixed(1) : '0.0';
    document.getElementById('avg-frontier-val').textContent = stats.avg_frontier_size ? stats.avg_frontier_size.toFixed(1) : '0.0';
    document.getElementById('max-frontier-val').textContent = stats.max_frontier_size || 0;
    document.getElementById('exploration-rate-val').textContent = stats.avg_exploration_rate ? (stats.avg_exploration_rate * 100).toFixed(1) + '%' : '0.0%';
    document.getElementById('avg-partitions-val').textContent = stats.avg_network_partitions ? stats.avg_network_partitions.toFixed(1) : '0.0';
    document.getElementById('max-partitions-val').textContent = stats.max_network_partitions || 0;
    document.getElementById('connectivity-val').textContent = stats.communication_connectivity ? (stats.communication_connectivity * 100).toFixed(1) + '%' : '0.0%';
}

function displayAggregatedStats(runs) {
    if (!runs || runs.length === 0) return;

    console.log("Calculating aggregated stats for", runs.length, "runs");
    console.log("Sample run data:", runs[0]);

    // Calculate aggregate statistics across all runs
    let totalSteps = 0;
    let successCount = 0;
    let totalDistance = 0;
    let totalIdleSteps = 0;
    let totalBacktracking = 0;
    let totalFrontierSize = 0;
    let maxFrontierSize = 0;
    let totalExplorationRate = 0;
    let totalNetworkPartitions = 0;
    let maxNetworkPartitions = 0;
    let totalConnectivity = 0;
    let totalTargetsFound = 0;

    runs.forEach(run => {
        totalSteps += run.steps || 0;
        if (run.success) successCount++;
        totalDistance += run.total_distance_traveled || 0;
        totalIdleSteps += run.total_idle_steps || 0;
        totalBacktracking += run.total_backtracking || 0;
        totalFrontierSize += run.avg_frontier_size || 0;
        maxFrontierSize = Math.max(maxFrontierSize, run.max_frontier_size || 0);
        totalExplorationRate += run.avg_exploration_rate || 0;
        totalNetworkPartitions += run.avg_network_partitions || 0;
        maxNetworkPartitions = Math.max(maxNetworkPartitions, run.max_network_partitions || 0);
        totalConnectivity += run.communication_connectivity || 0;
        totalTargetsFound += run.targets_found || 0;
    });

    const n = runs.length;
    const avgSteps = totalSteps / n;
    const avgDistance = totalDistance / n;
    const avgIdleSteps = totalIdleSteps / n;
    const avgBacktracking = totalBacktracking / n;
    const avgFrontierSize = totalFrontierSize / n;
    const avgExplorationRate = totalExplorationRate / n;
    const avgNetworkPartitions = totalNetworkPartitions / n;
    const avgConnectivity = totalConnectivity / n;

    // Store aggregated data for later display
    aggregatedStatsData = {
        steps: avgSteps.toFixed(0),
        targets: totalTargetsFound,
        success: ((successCount / n) * 100).toFixed(1) + '%',
        distance: avgDistance.toFixed(1),
        avg_distance: (avgDistance / (runs[0].num_drones || 1)).toFixed(1),
        idle_steps: avgIdleSteps.toFixed(0),
        avg_idle: (avgIdleSteps / (runs[0].num_drones || 1)).toFixed(1),
        backtracking: avgBacktracking.toFixed(0),
        avg_backtrack: (avgBacktracking / (runs[0].num_drones || 1)).toFixed(1),
        avg_frontier: avgFrontierSize.toFixed(1),
        max_frontier: maxFrontierSize,
        exploration_rate: (avgExplorationRate * 100).toFixed(1) + '%',
        avg_partitions: avgNetworkPartitions.toFixed(1),
        max_partitions: maxNetworkPartitions,
        connectivity: (avgConnectivity * 100).toFixed(1) + '%'
    };

    // Display the aggregated stats
    displayStoredAggregatedStats();
}

function displayAggregatedStatsFromSummary(summary) {
    if (!summary || summary.length === 0) return;

    // Aggregate stats across all policies
    let totalSteps = 0;
    let successCount = 0;
    let totalRuns = 0;
    let totalDistance = 0;
    let totalIdleSteps = 0;
    let totalBacktracking = 0;
    let totalFrontierSize = 0;
    let maxFrontierSize = 0;
    let totalExplorationRate = 0;
    let totalNetworkPartitions = 0;
    let maxNetworkPartitions = 0;
    let totalConnectivity = 0;
    let totalTargetsFound = 0;

    summary.forEach(item => {
        item.runs.forEach(run => {
            totalRuns++;
            totalSteps += run.steps || 0;
            if (run.success) successCount++;
            totalDistance += run.total_distance_traveled || 0;
            totalIdleSteps += run.total_idle_steps || 0;
            totalBacktracking += run.total_backtracking || 0;
            totalFrontierSize += run.avg_frontier_size || 0;
            maxFrontierSize = Math.max(maxFrontierSize, run.max_frontier_size || 0);
            totalExplorationRate += run.avg_exploration_rate || 0;
            totalNetworkPartitions += run.avg_network_partitions || 0;
            maxNetworkPartitions = Math.max(maxNetworkPartitions, run.max_network_partitions || 0);
            totalConnectivity += run.communication_connectivity || 0;
            totalTargetsFound += run.targets_found || 0;
        });
    });

    if (totalRuns === 0) return;

    const avgSteps = totalSteps / totalRuns;
    const avgDistance = totalDistance / totalRuns;
    const avgIdleSteps = totalIdleSteps / totalRuns;
    const avgBacktracking = totalBacktracking / totalRuns;
    const avgFrontierSize = totalFrontierSize / totalRuns;
    const avgExplorationRate = totalExplorationRate / totalRuns;
    const avgNetworkPartitions = totalNetworkPartitions / totalRuns;
    const avgConnectivity = totalConnectivity / totalRuns;

    // Store aggregated data for later display
    aggregatedStatsData = {
        steps: avgSteps.toFixed(0),
        targets: totalTargetsFound,
        success: ((successCount / totalRuns) * 100).toFixed(1) + '%',
        distance: avgDistance.toFixed(1),
        avg_distance: (avgDistance / (summary[0].runs[0]?.num_drones || 1)).toFixed(1),
        idle_steps: avgIdleSteps.toFixed(0),
        avg_idle: (avgIdleSteps / (summary[0].runs[0]?.num_drones || 1)).toFixed(1),
        backtracking: avgBacktracking.toFixed(0),
        avg_backtrack: (avgBacktracking / (summary[0].runs[0]?.num_drones || 1)).toFixed(1),
        avg_frontier: avgFrontierSize.toFixed(1),
        max_frontier: maxFrontierSize,
        exploration_rate: (avgExplorationRate * 100).toFixed(1) + '%',
        avg_partitions: avgNetworkPartitions.toFixed(1),
        max_partitions: maxNetworkPartitions,
        connectivity: (avgConnectivity * 100).toFixed(1) + '%'
    };

    // Display the aggregated stats
    displayStoredAggregatedStats();
}

function displayStoredAggregatedStats() {
    if (!aggregatedStatsData) {
        console.log("No aggregated stats data available");
        return;
    }

    console.log("Displaying aggregated stats:", aggregatedStatsData);

    // Update the DOM elements
    const stepsVal = document.getElementById('steps-val');
    const targetsVal = document.getElementById('targets-val');
    const successVal = document.getElementById('success-val');

    if (stepsVal) stepsVal.textContent = aggregatedStatsData.steps;
    if (targetsVal) targetsVal.textContent = aggregatedStatsData.targets;
    if (successVal) successVal.textContent = aggregatedStatsData.success;

    // Update new metrics
    const distanceVal = document.getElementById('distance-val');
    const avgDistanceVal = document.getElementById('avg-distance-val');
    const idleStepsVal = document.getElementById('idle-steps-val');
    const avgIdleVal = document.getElementById('avg-idle-val');
    const backtrackingVal = document.getElementById('backtracking-val');
    const avgBacktrackVal = document.getElementById('avg-backtrack-val');
    const avgFrontierVal = document.getElementById('avg-frontier-val');
    const maxFrontierVal = document.getElementById('max-frontier-val');
    const explorationRateVal = document.getElementById('exploration-rate-val');
    const avgPartitionsVal = document.getElementById('avg-partitions-val');
    const maxPartitionsVal = document.getElementById('max-partitions-val');
    const connectivityVal = document.getElementById('connectivity-val');

    if (distanceVal) distanceVal.textContent = aggregatedStatsData.distance;
    if (avgDistanceVal) avgDistanceVal.textContent = aggregatedStatsData.avg_distance;
    if (idleStepsVal) idleStepsVal.textContent = aggregatedStatsData.idle_steps;
    if (avgIdleVal) avgIdleVal.textContent = aggregatedStatsData.avg_idle;
    if (backtrackingVal) backtrackingVal.textContent = aggregatedStatsData.backtracking;
    if (avgBacktrackVal) avgBacktrackVal.textContent = aggregatedStatsData.avg_backtrack;
    if (avgFrontierVal) avgFrontierVal.textContent = aggregatedStatsData.avg_frontier;
    if (maxFrontierVal) maxFrontierVal.textContent = aggregatedStatsData.max_frontier;
    if (explorationRateVal) explorationRateVal.textContent = aggregatedStatsData.exploration_rate;
    if (avgPartitionsVal) avgPartitionsVal.textContent = aggregatedStatsData.avg_partitions;
    if (maxPartitionsVal) maxPartitionsVal.textContent = aggregatedStatsData.max_partitions;
    if (connectivityVal) connectivityVal.textContent = aggregatedStatsData.connectivity;
}

function setupCanvas(w, h) {
    const dpr = window.devicePixelRatio || 1;
    const pxW = w * CONFIG.cellSize;
    const pxH = h * CONFIG.cellSize;

    // Set internal resolution (sharpness)
    canvasTruth.width = pxW * dpr;
    canvasTruth.height = pxH * dpr;
    canvasBelief.width = pxW * dpr;
    canvasBelief.height = pxH * dpr;

    // Reset styles to allow CSS to handle responsive sizing
    // We only set max-width/height to natural size if we want to limit it,
    // but here we let flexbox handle it.
    canvasTruth.style.width = '';
    canvasTruth.style.height = '';
    canvasBelief.style.width = '';
    canvasBelief.style.height = '';

    // Normalize coordinate system
    ctxTruth.scale(dpr, dpr);
    ctxBelief.scale(dpr, dpr);

    // Ensure pixelated rendering for crisp grid
    ctxTruth.imageSmoothingEnabled = false;
    ctxBelief.imageSmoothingEnabled = false;
}

// Sidebar Toggling
window.toggleSidebar = function (side) {
    const sidebar = document.getElementById(side === 'left' ? 'sidebar' : 'right-sidebar');
    const toggleBtn = document.getElementById(side === 'left' ? 'toggle-left-btn' : 'toggle-right-btn');

    sidebar.classList.toggle('collapsed');

    // Show/Hide the collapsed-state trigger buttons
    if (sidebar.classList.contains('collapsed')) {
        toggleBtn.style.display = 'flex';
    } else {
        toggleBtn.style.display = 'none';
    }

    // Trigger resize after transition to ensure charts/canvas update if needed
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 350);
};

// View Switching
window.switchView = function (view) {
    const vizPanel = document.getElementById('viz-panel');
    const wrapperTruth = document.getElementById('wrapper-truth');
    const wrapperBelief = document.getElementById('wrapper-belief');
    const tabs = document.querySelectorAll('.view-tab');

    // Update Tabs
    tabs.forEach(tab => {
        if (tab.textContent.toLowerCase().includes(view.replace('split', 'split_view'))) {
            tab.classList.add('active');
        } else { // Handle slight mismatch in text vs id
            if ((view === 'truth' && tab.textContent.includes('TRUTH')) ||
                (view === 'belief' && tab.textContent.includes('BELIEF')) ||
                (view === 'split' && tab.textContent.includes('SPLIT'))) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        }
    });

    // Update Panel Mode
    vizPanel.classList.remove('single-view', 'split-view');

    if (view === 'split') {
        vizPanel.classList.add('split-view');
        wrapperTruth.style.display = 'flex';
        wrapperBelief.style.display = 'flex';
    } else {
        vizPanel.classList.add('single-view');
        if (view === 'truth') {
            wrapperTruth.style.display = 'flex';
            wrapperBelief.style.display = 'none';
        } else {
            wrapperTruth.style.display = 'none';
            wrapperBelief.style.display = 'flex';
        }
    }
};

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

    // Render targets from current state (enables visualization of moving targets)
    // Fall back to map.targets for backward compatibility with old simulation data
    const currentTargets = state.targets || map.targets;
    ctxTruth.fillStyle = CONFIG.colors.target;
    for (const [tx, ty] of currentTargets) {
        ctxTruth.beginPath();
        ctxTruth.arc(
            tx * CONFIG.cellSize + CONFIG.cellSize / 2,
            ty * CONFIG.cellSize + CONFIG.cellSize / 2,
            CONFIG.cellSize / 3, 0, Math.PI * 2
        );
        ctxTruth.fill();
    }

    // Draw Base Station
    const startX = map.start_pos ? map.start_pos[0] : 0;
    const startY = map.start_pos ? map.start_pos[1] : 0;
    ctxTruth.strokeStyle = CONFIG.colors.baseStation;
    ctxTruth.lineWidth = 3;
    ctxTruth.strokeRect(startX * CONFIG.cellSize + 2, startY * CONFIG.cellSize + 2, CONFIG.cellSize - 4, CONFIG.cellSize - 4);

    // Label Base
    ctxTruth.fillStyle = CONFIG.colors.baseStation;
    ctxTruth.font = `${CONFIG.cellSize / 2}px monospace`;
    ctxTruth.textAlign = 'center';
    ctxTruth.textBaseline = 'middle';
    ctxTruth.fillText('B', startX * CONFIG.cellSize + CONFIG.cellSize / 2, startY * CONFIG.cellSize + CONFIG.cellSize / 2);

    // Draw all drones with distinct colors
    if (state.positions && state.positions.length > 0) {
        state.positions.forEach((pos, index) => {
            drawAgent(ctxTruth, pos.x, pos.y, index, pos.battery);
        });
    } else {
        // Fallback for backward compatibility
        drawAgent(ctxTruth, state.x, state.y, 0);
    }
    renderGrid(ctxTruth, w, h);
}

function renderBeliefMap(state, map) {
    const w = map.width;
    const h = map.height;
    const belief = state.belief_map;

    ctxBelief.fillStyle = CONFIG.colors.unknown;
    ctxBelief.fillRect(0, 0, canvasBelief.width, canvasBelief.height);

    for (let y = 0; y < h; y++) {
        if (!belief[y]) continue; // Safety check
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

    // Draw Base Station (Belief)
    const startX = map.start_pos ? map.start_pos[0] : 0;
    const startY = map.start_pos ? map.start_pos[1] : 0;
    ctxBelief.strokeStyle = CONFIG.colors.baseStation;
    ctxBelief.lineWidth = 3;
    ctxBelief.strokeRect(startX * CONFIG.cellSize + 2, startY * CONFIG.cellSize + 2, CONFIG.cellSize - 4, CONFIG.cellSize - 4);

    // Label Base
    ctxBelief.fillStyle = CONFIG.colors.baseStation;
    ctxBelief.font = `${CONFIG.cellSize / 2}px monospace`;
    ctxBelief.textAlign = 'center';
    ctxBelief.textBaseline = 'middle';
    ctxBelief.fillText('B', startX * CONFIG.cellSize + CONFIG.cellSize / 2, startY * CONFIG.cellSize + CONFIG.cellSize / 2);

    // Draw all drones with distinct colors
    if (state.positions && state.positions.length > 0) {
        state.positions.forEach((pos, index) => {
            drawAgent(ctxBelief, pos.x, pos.y, index, pos.battery);
        });
    } else {
        // Fallback for backward compatibility
        drawAgent(ctxBelief, state.x, state.y, 0);
    }
    // Draw HUD -> Use HTML Panel
    if (typeof updateBatteryPanel === 'function') {
        updateBatteryPanel(state);
    }

    renderGrid(ctxBelief, w, h);
}

function updateBatteryPanel(state) {
    const panel = document.getElementById('battery-panel');
    if (!state.positions || state.positions.length === 0) {
        panel.innerHTML = '';
        return;
    }

    // Sync number of cards with number of drones
    const drones = state.positions;
    let cards = panel.getElementsByClassName('battery-card');

    // Simple sync: if counts mismatch, just clear and rebuild.
    // For small number of drones this is fine.
    if (cards.length !== drones.length) {
        panel.innerHTML = '';
        drones.forEach((_, i) => {
            const card = document.createElement('div');
            card.className = 'battery-card';
            card.innerHTML = `
                <div class="bat-header">
                    <span>DRONE ${i + 1}</span>
                    <span class="bat-pct">100%</span>
                </div>
                <div class="bat-bar-container">
                    <div class="bat-fill high"></div>
                </div>
            `;
            panel.appendChild(card);
        });
        cards = panel.getElementsByClassName('battery-card');
    }

    // Update each card
    drones.forEach((pos, i) => {
        const battery = pos.battery || 0;
        const maxBat = pos.max_battery || 500;
        const pct = Math.max(0, Math.min(1, battery / maxBat));
        const pctInt = Math.round(pct * 100);

        const card = cards[i];
        if (!card) return;

        const pctText = card.querySelector('.bat-pct');
        const fill = card.querySelector('.bat-fill');

        pctText.textContent = `${pctInt}%`;
        fill.style.width = `${pctInt}%`;

        // Update color class
        fill.className = 'bat-fill'; // reset
        if (pct > 0.5) fill.classList.add('high');
        else if (pct > 0.2) fill.classList.add('med');
        else fill.classList.add('low');

        if (pos.is_dead) {
            pctText.textContent = "DEAD";
            fill.style.width = '0%';
            card.style.opacity = '0.5';
        } else {
            card.style.opacity = '1';
        }
    });
}

function drawAgent(ctx, x, y, droneIndex = 0, battery = 1000) {
    // Use distinct color for each drone
    const color = CONFIG.droneColors[droneIndex % CONFIG.droneColors.length];
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(
        x * CONFIG.cellSize + CONFIG.cellSize / 2,
        y * CONFIG.cellSize + CONFIG.cellSize / 2,
        CONFIG.cellSize / 2.5, 0, Math.PI * 2
    );
    ctx.fill();

    // Add drone index label for multi-drone scenarios
    if (droneIndex > 0 || (simulationData && simulationData.config && simulationData.config.num_drones > 1)) {
        ctx.fillStyle = '#000';
        ctx.font = `${CONFIG.cellSize / 2}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(
            (droneIndex + 1).toString(),
            x * CONFIG.cellSize + CONFIG.cellSize / 2,
            y * CONFIG.cellSize + CONFIG.cellSize / 2
        );
    }
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
