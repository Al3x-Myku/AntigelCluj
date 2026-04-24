/**
 * PhishGuard — Chart.js Helper Functions
 * Shared utilities for creating dashboard charts.
 */

const CHART_COLORS = {
    red: 'rgba(239, 68, 68, 0.8)',
    redBg: 'rgba(239, 68, 68, 0.15)',
    blue: 'rgba(59, 130, 246, 0.8)',
    blueBg: 'rgba(59, 130, 246, 0.15)',
    green: 'rgba(16, 185, 129, 0.8)',
    greenBg: 'rgba(16, 185, 129, 0.15)',
    yellow: 'rgba(245, 158, 11, 0.8)',
    yellowBg: 'rgba(245, 158, 11, 0.15)',
    purple: 'rgba(139, 92, 246, 0.8)',
    purpleBg: 'rgba(139, 92, 246, 0.15)',
    pink: 'rgba(236, 72, 153, 0.8)',
    pinkBg: 'rgba(236, 72, 153, 0.15)',
    cyan: 'rgba(6, 182, 212, 0.8)',
    cyanBg: 'rgba(6, 182, 212, 0.15)',
    orange: 'rgba(249, 115, 22, 0.8)',
    orangeBg: 'rgba(249, 115, 22, 0.15)',
};

const CHANNEL_COLORS = {
    email: CHART_COLORS.blue,
    sms: CHART_COLORS.green,
    whatsapp: CHART_COLORS.green,
    telegram: CHART_COLORS.cyan,
    discord: CHART_COLORS.purple,
    instagram: CHART_COLORS.pink,
};

const DARK_THEME = {
    color: 'rgba(255,255,255,0.7)',
    gridColor: 'rgba(255,255,255,0.06)',
    borderColor: 'rgba(255,255,255,0.1)',
};

/* Set Chart.js global defaults for dark mode */
function setChartDefaults() {
    Chart.defaults.color = DARK_THEME.color;
    Chart.defaults.borderColor = DARK_THEME.borderColor;
    Chart.defaults.plugins.legend.labels.color = DARK_THEME.color;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.padding = 16;
    Chart.defaults.elements.bar.borderRadius = 6;
    Chart.defaults.elements.line.tension = 0.4;
}
setChartDefaults();

/**
 * Create a funnel chart (horizontal bar chart).
 */
function createFunnelChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const labels = data.map(d => d.stage);
    const values = data.map(d => d.count);
    const colors = [CHART_COLORS.blue, CHART_COLORS.cyan, CHART_COLORS.yellow, CHART_COLORS.red];

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 8,
                barPercentage: 0.7,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: DARK_THEME.gridColor }, ticks: { color: DARK_THEME.color } },
                y: { grid: { display: false }, ticks: { color: DARK_THEME.color, font: { size: 13, weight: 600 } } },
            },
        },
    });
}

/**
 * Create a per-channel bar chart.
 */
function createChannelChart(canvasId, perChannel) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const channels = Object.keys(perChannel);
    const sent = channels.map(ch => perChannel[ch].sent);
    const clicked = channels.map(ch => perChannel[ch].clicked);
    const submitted = channels.map(ch => perChannel[ch].submitted);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: channels.map(ch => ch.charAt(0).toUpperCase() + ch.slice(1)),
            datasets: [
                { label: 'Sent', data: sent, backgroundColor: CHART_COLORS.blue, borderRadius: 6 },
                { label: 'Clicked', data: clicked, backgroundColor: CHART_COLORS.yellow, borderRadius: 6 },
                { label: 'Submitted', data: submitted, backgroundColor: CHART_COLORS.red, borderRadius: 6 },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: DARK_THEME.gridColor }, beginAtZero: true },
            },
        },
    });
}

/**
 * Create a timeline line chart.
 */
function createTimelineChart(canvasId, timeline) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const sortedKeys = Object.keys(timeline).sort();
    const allChannels = new Set();
    sortedKeys.forEach(k => Object.keys(timeline[k]).forEach(ch => allChannels.add(ch)));

    const datasets = [];
    const colorArr = [CHART_COLORS.blue, CHART_COLORS.green, CHART_COLORS.cyan, CHART_COLORS.purple, CHART_COLORS.pink, CHART_COLORS.orange];
    let i = 0;
    allChannels.forEach(ch => {
        datasets.push({
            label: ch.charAt(0).toUpperCase() + ch.slice(1),
            data: sortedKeys.map(k => timeline[k][ch] || 0),
            borderColor: colorArr[i % colorArr.length],
            backgroundColor: colorArr[i % colorArr.length].replace('0.8', '0.1'),
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 7,
        });
        i++;
    });

    return new Chart(ctx, {
        type: 'line',
        data: { labels: sortedKeys, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { grid: { color: DARK_THEME.gridColor }, ticks: { maxRotation: 45 } },
                y: { grid: { color: DARK_THEME.gridColor }, beginAtZero: true },
            },
        },
    });
}

/**
 * Create a histogram for anomaly scores.
 */
function createHistogram(canvasId, scores, threshold) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    // Create bins
    const maxScore = Math.max(...scores, threshold * 1.5) || 50;
    const nBins = 20;
    const binWidth = maxScore / nBins;
    const bins = new Array(nBins).fill(0);
    const labels = [];

    scores.forEach(s => {
        const idx = Math.min(Math.floor(s / binWidth), nBins - 1);
        bins[idx]++;
    });

    for (let i = 0; i < nBins; i++) {
        labels.push((i * binWidth).toFixed(1));
    }

    const colors = bins.map((_, i) => {
        const midpoint = (i + 0.5) * binWidth;
        return midpoint > threshold ? CHART_COLORS.red : CHART_COLORS.green;
    });

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Events',
                data: bins,
                backgroundColor: colors,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                annotation: threshold ? {
                    annotations: {
                        threshold: {
                            type: 'line',
                            xMin: Math.floor(threshold / binWidth),
                            xMax: Math.floor(threshold / binWidth),
                            borderColor: CHART_COLORS.red,
                            borderWidth: 2,
                            borderDash: [6, 3],
                            label: { display: true, content: 'Threshold', position: 'start', color: '#fff' },
                        }
                    }
                } : {},
            },
            scales: {
                x: { grid: { display: false }, title: { display: true, text: 'Mahalanobis Distance', color: DARK_THEME.color } },
                y: { grid: { color: DARK_THEME.gridColor }, title: { display: true, text: 'Count', color: DARK_THEME.color } },
            },
        },
    });
}

/**
 * Create a doughnut chart.
 */
function createDoughnut(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 8 }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: { legend: { position: 'bottom' } },
        },
    });
}

/* Utility: format large numbers */
function formatNum(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toString();
}

/* Utility: status badge */
function statusBadge(status) {
    const colors = {
        active: 'success', frozen: 'danger', revoked: 'danger',
        suspended: 'warning', expired: 'secondary',
        draft: 'secondary', queued: 'info', running: 'primary',
        completed: 'success', failed: 'danger',
        pending: 'secondary', sent: 'info', clicked: 'warning', submitted: 'danger',
    };
    return `<span class="badge bg-${colors[status] || 'secondary'}">${status}</span>`;
}
