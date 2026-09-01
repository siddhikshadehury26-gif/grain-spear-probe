/**
 * app.js - Frontend Controller for GrainGuard IoT Dashboard
 * Handles real-time polling, Chart.js multi-spectral rendering, FEFO priority queues,
 * and live interactive hackathon demo trigger sequences.
 */

let containersData = [];
let currentFilter = 'ALL';
let currentModalContainerId = null;
let timeSeriesChartInstance = null;
let pollingInterval = null;

// Initialize on window load
document.addEventListener('DOMContentLoaded', () => {
    fetchWarehouseData();
    // Start automated 2.5-second polling loop
    pollingInterval = setInterval(fetchWarehouseData, 2500);
});

/**
 * Fetches all container states and warehouse KPIs
 */
async function fetchWarehouseData() {
    try {
        const [containersRes, summaryRes] = await Promise.all([
            fetch('/api/containers'),
            fetch('/api/summary')
        ]);

        if (containersRes.ok && summaryRes.ok) {
            const containersJson = await containersRes.json();
            const summaryJson = await summaryRes.json();

            containersData = containersJson.containers || [];
            updateSummaryKPIs(summaryJson);
            renderFEFOTable(containersData);
            renderContainerCards(containersData);
            updateFilterCounts(containersData);

            // Update modal if currently opened
            if (currentModalContainerId) {
                const activeContainer = containersData.find(c => c.container_id === currentModalContainerId);
                if (activeContainer) {
                    refreshModalData(activeContainer);
                }
            }

            document.getElementById('connectionStatus').textContent = 'ACTIVE (2.5s live polling)';
            document.getElementById('connectionStatus').className = 'hud-value status-online';
        }
    } catch (err) {
        console.error('Error polling telemetry data:', err);
        document.getElementById('connectionStatus').textContent = 'DISCONNECTED (Retrying...)';
        document.getElementById('connectionStatus').className = 'hud-value text-critical';
    }
}

/**
 * Updates top summary KPI badges & Critical Alert Banner
 */
function updateSummaryKPIs(summary) {
    document.getElementById('kpiTotalStock').textContent = summary.total_stock_tons || '0.0';
    document.getElementById('kpiTotalUnits').textContent = `${summary.total_monitored_units || 0} Storage Units Monitored`;

    document.getElementById('kpiAtRiskStock').textContent = summary.at_risk_tons || '0.0';
    document.getElementById('kpiAtRiskBreakdown').textContent = 
        `${summary.critical_units || 0} Critical, ${summary.warning_units || 0} Warning`;

    document.getElementById('kpiMeanCO2').textContent = summary.mean_headspace_co2 || '420.0';

    const topRank = summary.top_fefo_priority;
    if (topRank) {
        document.getElementById('kpiTopRankUnit').textContent = `${topRank.container_id} (${topRank.grain_type})`;
        document.getElementById('kpiTopRankDTS').textContent = `Days to Spoilage: ${topRank.days_to_spoilage} Days`;
    }

    // Critical Alert Banner logic
    const banner = document.getElementById('criticalAlertBanner');
    if (summary.critical_units > 0 && topRank && topRank.status === 'CRITICAL') {
        banner.style.display = 'block';
        document.getElementById('criticalAlertTitle').textContent = 
            `🚨 CRITICAL SPOILAGE ALERT: ${topRank.container_id} (${topRank.grain_type}) REQUIRES IMMEDIATE DISPATCH`;
        document.getElementById('criticalAlertDesc').textContent = 
            `Headspace CO₂ reached ${Math.round(topRank.headspace_co2)} ppm with active inside-out bio-heat. Estimated Spoilage: ${topRank.days_to_spoilage} Days.`;
    } else {
        banner.style.display = 'none';
    }
}

/**
 * Renders the FEFO Priority Dispatch Queue Table
 */
function renderFEFOTable(containers) {
    const tbody = document.getElementById('fefoTableBody');
    if (!tbody) return;

    if (!containers || containers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center" style="padding: 2rem; color: var(--text-muted);">No grain storage units registered.</td></tr>`;
        return;
    }

    let html = '';
    containers.forEach((c) => {
        const isRankOne = c.fefo_rank === 1;
        const rankBadgeClass = isRankOne ? 'rank-top-1' : 'rank-standard';
        
        let statusBadgeClass = 'badge-optimal';
        if (c.status === 'CRITICAL') statusBadgeClass = 'badge-critical';
        else if (c.status === 'WARNING') statusBadgeClass = 'badge-warning';
        else if (c.status === 'ELEVATED') statusBadgeClass = 'badge-elevated';

        const co2Color = c.headspace_co2 > 1800 ? 'text-critical font-bold' : (c.headspace_co2 > 900 ? 'highlight-amber' : 'highlight-cyan');
        const dtsColor = c.days_to_spoilage <= 3.0 ? 'text-critical font-bold' : (c.days_to_spoilage <= 14.0 ? 'highlight-amber' : 'highlight-emerald');

        html += `
            <tr onclick="openContainerModal('${c.container_id}')" style="cursor: pointer;">
                <td class="text-center">
                    <span class="fefo-rank-badge ${rankBadgeClass}">#${c.fefo_rank}</span>
                </td>
                <td>
                    <strong style="color: #fff;">${c.container_id}</strong>
                    <div style="font-size: 0.72rem; color: var(--text-muted);">${c.storage_type || 'Spear Probe'}</div>
                </td>
                <td><span class="tag">${c.grain_type}</span></td>
                <td class="font-mono"><strong>${c.capacity_tons}</strong> t</td>
                <td class="font-mono ${co2Color}">${Math.round(c.headspace_co2)} ppm</td>
                <td class="font-mono">
                    ${c.temperature}°C 
                    <small style="color: ${c.differential_matrix.delta_temp > 1.5 ? '#f87171' : 'var(--text-muted)'}">
                        (ΔT: ${c.differential_matrix.delta_temp > 0 ? '+' : ''}${c.differential_matrix.delta_temp}°C)
                    </small>
                </td>
                <td class="font-mono">${c.humidity}%</td>
                <td class="font-mono ${dtsColor}">
                    <strong>${c.days_to_spoilage} Days</strong>
                    ${c.early_lead_days > 0 ? `<div style="font-size: 0.68rem; color: #38bdf8;">⚡ +${c.early_lead_days}d Lead</div>` : ''}
                </td>
                <td><span class="badge ${statusBadgeClass}">${c.status}</span></td>
                <td>
                    <button class="btn btn-action-sm ${c.status === 'CRITICAL' ? 'btn-danger-glow' : 'btn-secondary'}" 
                            onclick="event.stopPropagation(); executeDispatch('${c.container_id}')">
                        <i class="fa-solid fa-truck-fast"></i> Dispatch
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

/**
 * Renders the Visual Container Health Cards Grid
 */
function renderContainerCards(containers) {
    const grid = document.getElementById('containerCardsGrid');
    if (!grid) return;

    const filtered = containers.filter(c => {
        if (currentFilter === 'ALL') return true;
        return c.status === currentFilter;
    });

    if (filtered.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">No containers found matching filter "${currentFilter}".</div>`;
        return;
    }

    let html = '';
    filtered.forEach(c => {
        let cardStatusClass = 'card-optimal';
        let badgeClass = 'badge-optimal';
        if (c.status === 'CRITICAL') { cardStatusClass = 'card-critical'; badgeClass = 'badge-critical'; }
        else if (c.status === 'WARNING') { cardStatusClass = 'card-warning'; badgeClass = 'badge-warning'; }
        else if (c.status === 'ELEVATED') { cardStatusClass = 'card-elevated'; badgeClass = 'badge-elevated'; }

        html += `
            <div class="container-card glass-panel ${cardStatusClass}" onclick="openContainerModal('${c.container_id}')">
                <div class="card-top">
                    <div class="card-title-wrap">
                        <h3>${c.container_id}</h3>
                        <span class="card-grain-label">${c.grain_type} • ${c.capacity_tons} Tons</span>
                    </div>
                    <div style="display: flex; gap: 0.4rem; align-items: center;">
                        <span class="badge ${badgeClass}">${c.status}</span>
                        <span class="fefo-rank-badge ${c.fefo_rank === 1 ? 'rank-top-1' : 'rank-standard'}" style="width: 26px; height: 26px; font-size: 0.75rem;">
                            #${c.fefo_rank}
                        </span>
                    </div>
                </div>

                <div class="card-metrics-grid">
                    <!-- Headspace CO2 (Respiration) -->
                    <div class="metric-cell">
                        <div class="metric-header">
                            <span><i class="fa-solid fa-wind"></i> Headspace CO₂</span>
                            <span style="color: #22d3ee; font-weight: 600;">Respiration</span>
                        </div>
                        <div class="metric-value ${c.headspace_co2 > 1800 ? 'text-critical' : 'highlight-cyan'}">
                            ${Math.round(c.headspace_co2)} <small style="font-size: 0.7rem;">ppm</small>
                        </div>
                        <div class="metric-sub">
                            ${c.delta_co2_rate > 0 ? `+${c.delta_co2_rate} ppm/Δt` : 'Stable flux'}
                        </div>
                    </div>

                    <!-- Core Temp & Diff Matrix -->
                    <div class="metric-cell">
                        <div class="metric-header">
                            <span><i class="fa-solid fa-temperature-half"></i> Core Temp</span>
                            <span style="color: #fca5a5;">Inside-Out</span>
                        </div>
                        <div class="metric-value">
                            ${c.temperature}°C
                        </div>
                        <div class="metric-sub">
                            ΔT: ${c.differential_matrix.delta_temp > 0 ? '+' : ''}${c.differential_matrix.delta_temp}°C vs Amb
                        </div>
                    </div>

                    <!-- Equilibrium RH -->
                    <div class="metric-cell">
                        <div class="metric-header">
                            <span><i class="fa-solid fa-droplet"></i> Equilibrium RH</span>
                            <span>Equilibrium</span>
                        </div>
                        <div class="metric-value ${c.humidity > 70 ? 'highlight-amber' : ''}">
                            ${c.humidity}%
                        </div>
                        <div class="metric-sub">Safe limit < 65%</div>
                    </div>

                    <!-- Core Dampness Probe -->
                    <div class="metric-cell">
                        <div class="metric-header">
                            <span><i class="fa-solid fa-water"></i> Core Moisture</span>
                            <span>Capacitive</span>
                        </div>
                        <div class="metric-value ${c.core_moisture > 15 ? 'text-critical' : ''}">
                            ${c.core_moisture}%
                        </div>
                        <div class="metric-sub">Safe limit < 14.5%</div>
                    </div>
                </div>

                <div class="card-dts-pill">
                    <div>
                        <span style="color: var(--text-muted);">Days to Spoilage (DTS):</span>
                        <strong class="dts-val ${c.days_to_spoilage <= 3.0 ? 'text-critical' : (c.days_to_spoilage <= 14.0 ? 'highlight-amber' : 'highlight-emerald')}">
                            ${c.days_to_spoilage} Days
                        </strong>
                    </div>
                    ${c.early_lead_days > 0 ? `<span class="tag" style="background: rgba(6, 182, 212, 0.2); color: #22d3ee;">⚡ +${c.early_lead_days}d Lead</span>` : ''}
                </div>

                <div class="card-footer-actions">
                    <span style="font-size: 0.72rem; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap; max-width: 200px;">
                        ${c.action_label}
                    </span>
                    <button class="btn btn-secondary btn-action-sm" onclick="event.stopPropagation(); openContainerModal('${c.container_id}')">
                        <i class="fa-solid fa-chart-line"></i> Deep Dive
                    </button>
                </div>
            </div>
        `;
    });

    grid.innerHTML = html;
}

/**
 * Updates filter tab counts
 */
function updateFilterCounts(containers) {
    document.getElementById('countAll').textContent = containers.length;
    document.getElementById('countCritical').textContent = containers.filter(c => c.status === 'CRITICAL').length;
    document.getElementById('countWarning').textContent = containers.filter(c => c.status === 'WARNING').length;
    document.getElementById('countOptimal').textContent = containers.filter(c => c.status === 'OPTIMAL').length;
}

/**
 * Filter tab click handler
 */
function filterCards(filter) {
    currentFilter = filter;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.toUpperCase().startsWith(filter)) {
            btn.classList.add('active');
        }
    });
    renderContainerCards(containersData);
}

/**
 * Triggers interactive simulation events (Breath Exhale, Solar Wave, etc.)
 */
async function triggerSimulationEvent(eventType) {
    const targetUnit = document.getElementById('demoTargetUnit').value || 'SPEAR-D01';
    const ticker = document.getElementById('demoFeedbackMessage');
    ticker.textContent = `Injecting event "${eventType}" into ${targetUnit}...`;

    try {
        const res = await fetch('/api/simulate/event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event: eventType, container_id: targetUnit })
        });

        const data = await res.json();
        if (data.status === 'success') {
            ticker.textContent = `✓ ${data.message}`;
            // Immediately refresh data
            await fetchWarehouseData();
        } else {
            ticker.textContent = `✗ Error: ${data.message}`;
        }
    } catch (e) {
        ticker.textContent = `✗ Network Error triggering simulation: ${e}`;
    }
}

/**
 * Dispatches a container to milling plant (FEFO execution)
 */
async function executeDispatch(containerId) {
    if (!confirm(`Confirm FEFO Dispatch of ${containerId} for immediate milling / processing?`)) return;

    try {
        const res = await fetch(`/api/dispatch/${containerId}`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            document.getElementById('demoFeedbackMessage').textContent = `✓ ${data.message}`;
            if (currentModalContainerId === containerId) {
                closeDetailModal();
            }
            await fetchWarehouseData();
        }
    } catch (e) {
        alert('Error dispatching container: ' + e);
    }
}

/**
 * Quick dispatch for Rank #1 from alert banner
 */
function quickDispatchRankOne() {
    if (containersData.length > 0) {
        executeDispatch(containersData[0].container_id);
    }
}

/**
 * Opens Deep-Dive Analytical Chart & Diagnostic Modal
 */
async function openContainerModal(containerId) {
    currentModalContainerId = containerId;
    const modal = document.getElementById('detailModal');
    modal.style.display = 'flex';

    try {
        const res = await fetch(`/api/containers/${containerId}`);
        if (res.ok) {
            const data = await res.json();
            refreshModalData(data.container);
        }
    } catch (e) {
        console.error('Error fetching container details for modal:', e);
    }
}

/**
 * Refreshes modal content & Chart.js graph
 */
function refreshModalData(c) {
    document.getElementById('modalContainerTitle').textContent = `${c.container_id} - Multi-Spectral Spoilage Analysis`;
    document.getElementById('modalGrainType').textContent = `${c.grain_type} • ${c.capacity_tons} Tons • Storage: ${c.storage_type || 'Spear Probe'}`;

    const badge = document.getElementById('modalStatusBadge');
    badge.textContent = `${c.status} (FEFO Rank #${c.fefo_rank || 1})`;
    badge.className = `modal-badge badge-${c.status.toLowerCase()}`;

    // Differential Matrix Banner
    const diff = c.differential_matrix || {};
    document.getElementById('modalDiffClassification').textContent = diff.classification || 'ISOTHERMAL EQUILIBRIUM';
    document.getElementById('modalDiffExplanation').textContent = diff.explanation || '';

    // Metrics
    document.getElementById('modalValCO2').textContent = `${Math.round(c.headspace_co2)} ppm`;
    document.getElementById('modalDeltaCO2').textContent = c.delta_co2_rate > 0 ? `+${c.delta_co2_rate} ppm/Δt (Active flux)` : 'Stable baseline';

    document.getElementById('modalValTemp').innerHTML = `${c.temperature}°C <small style="font-size: 0.8rem; color: var(--text-muted);">/ Amb: ${c.ambient_temp}°C</small>`;
    document.getElementById('modalDeltaTemp').textContent = `ΔT = ${diff.delta_temp > 0 ? '+' : ''}${diff.delta_temp}°C (${diff.is_solar_heating ? 'Solar Outside-In' : 'Inside-Out Bio-Heat'})`;

    document.getElementById('modalValRH').textContent = `${c.humidity}%`;
    document.getElementById('modalValMoist').textContent = `${c.core_moisture}%`;

    // Root Causes
    const rootList = document.getElementById('modalRootCausesList');
    if (c.root_causes && c.root_causes.length > 0) {
        rootList.innerHTML = c.root_causes.map(rc => `<li>${rc}</li>`).join('');
    } else {
        rootList.innerHTML = `<li>All multi-spectral telemetry within certified safe baseline.</li>`;
    }

    document.getElementById('modalDTS').textContent = `${c.days_to_spoilage} Days`;

    // Render Time-Series Chart
    renderLeadCurveChart(c.history || []);
}

/**
 * Renders the Chart.js Multi-Spectral Time Series showing 3-5 day CO2 Lead vs Thermal Lag
 */
function renderLeadCurveChart(history) {
    const ctx = document.getElementById('timeSeriesChart');
    if (!ctx) return;

    const labels = history.map(h => h.timestamp);
    const co2Data = history.map(h => h.headspace_co2);
    const tempData = history.map(h => h.temperature);
    const ambData = history.map(h => h.ambient_temp);

    if (timeSeriesChartInstance) {
        timeSeriesChartInstance.destroy();
    }

    timeSeriesChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Headspace CO₂ (ppm) [Metabolic Respiration]',
                    data: co2Data,
                    borderColor: '#22d3ee',
                    backgroundColor: 'rgba(34, 211, 238, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.35,
                    yAxisID: 'yCO2'
                },
                {
                    label: 'Core Temperature (°C) [Thermal Lag]',
                    data: tempData,
                    borderColor: '#f87171',
                    backgroundColor: 'transparent',
                    borderWidth: 2.5,
                    borderDash: [4, 4],
                    tension: 0.35,
                    yAxisID: 'yTemp'
                },
                {
                    label: 'Ambient Wall Temp (°C) [Solar Flux]',
                    data: ambData,
                    borderColor: '#fbbf24',
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    tension: 0.35,
                    yAxisID: 'yTemp'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: false // Using custom top legend
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#64748b', font: { size: 10 } }
                },
                yCO2: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#22d3ee', font: { size: 10 } },
                    title: { display: true, text: 'CO₂ Respiration (ppm)', color: '#22d3ee', font: { size: 11 } }
                },
                yTemp: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#f87171', font: { size: 10 } },
                    title: { display: true, text: 'Temperature (°C)', color: '#f87171', font: { size: 11 } }
                }
            }
        }
    });
}

/**
 * Closes Deep-Dive Modal
 */
function closeDetailModal() {
    currentModalContainerId = null;
    document.getElementById('detailModal').style.display = 'none';
}

function dispatchCurrentModalUnit() {
    if (currentModalContainerId) {
        executeDispatch(currentModalContainerId);
    }
}
