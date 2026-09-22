/* ============================================
   Pixel Labs Network Builder - Application JS
   ============================================ */

const API_BASE = '/api';
let currentPersonId = null;

// ======== NAVIGATION ========
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

    const targetPage = document.getElementById(`page-${page}`);
    if (targetPage) targetPage.style.display = 'block';

    const links = document.querySelectorAll('.nav-link');
    links.forEach(link => {
        if (link.textContent.toLowerCase().includes(page === 'dashboard' ? 'dashboard' : page === 'import' ? 'import' : page === 'queue' ? 'queue' : page === 'history' ? 'history' : 'settings')) {
            link.classList.add('active');
        }
    });

    if (page === 'dashboard') loadDashboard();
    if (page === 'queue') loadQueue();
    if (page === 'import') {}
    if (page === 'history') loadHistory();
    if (page === 'settings') loadSettings();
}

// ======== TOAST ========
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ======== API HELPERS ========
async function apiGet(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        return await res.json();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        return null;
    }
}

async function apiPost(endpoint, data) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return await res.json();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        return null;
    }
}

async function apiPut(endpoint, data) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return await res.json();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        return null;
    }
}

async function apiDelete(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
        return await res.json();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        return null;
    }
}

async function apiUpload(endpoint, formData) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            body: formData,
        });
        return await res.json();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        return null;
    }
}

// ======== DASHBOARD ========
async function loadDashboard() {
    const data = await apiGet('/dashboard');
    if (!data) return;

    document.getElementById('today-date').textContent = new Date().toLocaleDateString('en-US', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });

    // Stats
    animateNumber('stat-total', data.total_researched);
    animateNumber('stat-sent', data.total_connection_sent);
    animateNumber('stat-connected', data.total_connected);
    animateNumber('stat-followups', data.total_follow_ups);

    // Network Balance
    renderBalance(data);

    // Queue
    renderQueue(data.queue);

    // High Relevance
    renderHighRelevance(data.queue);
}

function animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    const current = parseInt(el.textContent) || 0;
    if (current === target) { el.textContent = target; return; }
    const step = target > current ? 1 : -1;
    const timer = setInterval(() => {
        el.textContent = parseInt(el.textContent) + step;
        if (parseInt(el.textContent) === target) clearInterval(timer);
    }, 30);
}

function renderBalance(data) {
    const balance = data.network_balance || {};
    const messageEl = document.getElementById('balance-message');
    const barEl = document.getElementById('balance-bar');
    const legendEl = document.getElementById('balance-legend');
    const recsEl = document.getElementById('balance-recommendations');

    const colors = {
        CLIENT: '#2563eb',
        REFERRAL_PARTNER: '#059669',
        AGENCY_BUSINESS: '#7c3aed',
        PROFESSIONAL_NETWORK: '#6b7280',
    };

    const labels = {
        CLIENT: 'Clients',
        REFERRAL_PARTNER: 'Referral Partners',
        AGENCY_BUSINESS: 'Agency / Business',
        PROFESSIONAL_NETWORK: 'Professional Network',
    };

    let barHtml = '';
    let legendHtml = '';
    let total = 0;
    const counts = {};

    for (const [cat, pct] of Object.entries(balance)) {
        counts[cat] = pct;
        total += pct;
    }

    if (total === 0) {
        messageEl.textContent = 'No prospects yet. Import or add prospects to build your network.';
        barEl.innerHTML = '<div style="width:100%; background: var(--gray-200);">Empty</div>';
        return;
    }

    const balanceMsg = data.current_targets || {};
    messageEl.textContent = data.queue ? data.queue.message || 'Network Balance Overview' : '';

    // Build bar
    for (const [cat, pct] of Object.entries(balance)) {
        if (pct > 0) {
            barHtml += `<div class="balance-segment" style="width:${pct}%; background:${colors[cat] || '#6b7280'};">${pct}%</div>`;
            legendHtml += `<div class="legend-item"><div class="legend-dot" style="background:${colors[cat] || '#6b7280'};"></div>${labels[cat] || cat}: ${pct}%</div>`;
        }
    }

    barEl.innerHTML = barHtml || '<div style="width:100%; background: var(--gray-200);">No data</div>';
    legendEl.innerHTML = legendHtml;

    // Recommendations
    const recommendations = [];
    const clientPct = balance.CLIENT || 0;
    const refPct = balance.REFERRAL_PARTNER || 0;
    const agencyPct = balance.AGENCY_BUSINESS || 0;
    const profPct = balance.PROFESSIONAL_NETWORK || 0;

    if (clientPct > 50) {
        recommendations.push('<p style="color: var(--warning);">⚠️ Your network is heavily concentrated in potential clients.</p>');
        recommendations.push('<p style="font-size: 13px; color: var(--gray-500);">Consider adding more referral partners and agency connections for a balanced network.</p>');
    } else if (clientPct < 20 && total > 5) {
        recommendations.push('<p style="color: var(--warning);">⚠️ Few potential clients in your network.</p>');
    } else {
        recommendations.push('<p style="color: var(--success);">✅ Your network is well balanced across categories.</p>');
    }

    recsEl.innerHTML = recommendations.join('');
}

function renderQueue(queueData) {
    const container = document.getElementById('queue-container');
    if (!queueData || !queueData.queue) {
        container.innerHTML = '<div class="empty-state"><p>No queue data available</p></div>';
        return;
    }

    const colors = { CLIENT: '#dbeafe', REFERRAL_PARTNER: '#d1fae5', AGENCY_BUSINESS: '#ede9fe', PROFESSIONAL_NETWORK: '#f3f4f6', OTHER: '#f3f4f6' };
    const badgeClasses = { CLIENT: 'badge-client', REFERRAL_PARTNER: 'badge-referral', AGENCY_BUSINESS: 'badge-agency', PROFESSIONAL_NETWORK: 'badge-professional', OTHER: 'badge-other' };

    let html = '';
    const sections = Object.entries(queueData.queue);

    for (const [sectionName, items] of sections) {
        const count = items.length;
        html += `<div class="queue-section">`;
        html += `<div class="queue-section-header">
            <h3>${sectionName}</h3>
            <span class="queue-count">${count}</span>
        </div>`;

        if (count === 0) {
            html += '<div style="padding: 16px; color: var(--gray-500); font-size: 14px;">No prospects in this category</div>';
        } else {
            html += '<div style="display: flex; flex-direction: column; gap: 12px;">';
            items.forEach(item => {
                html += renderProspectCard(item, false, colors, badgeClasses);
            });
            html += '</div>';
        }
        html += '</div>';
    }

    container.innerHTML = html;
}

function renderQueueFull(queueData) {
    const container = document.getElementById('queue-full-container');
    if (!queueData || !queueData.queue) {
        container.innerHTML = '<div class="empty-state"><p>No queue data available</p></div>';
        return;
    }

    const colors = { CLIENT: '#dbeafe', REFERRAL_PARTNER: '#d1fae5', AGENCY_BUSINESS: '#ede9fe', PROFESSIONAL_NETWORK: '#f3f4f6', OTHER: '#f3f4f6' };
    const badgeClasses = { CLIENT: 'badge-client', REFERRAL_PARTNER: 'badge-referral', AGENCY_BUSINESS: 'badge-agency', PROFESSIONAL_NETWORK: 'badge-professional', OTHER: 'badge-other' };

    let html = '';

    for (const [sectionName, items] of Object.entries(queueData.queue)) {
        html += `<div class="queue-section">`;
        html += `<div class="queue-section-header">
            <h3>${sectionName}</h3>
            <span class="queue-count">${items.length}</span>
        </div>`;
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 16px;">';
        items.forEach(item => {
            html += renderProspectCard(item, true, colors, badgeClasses);
        });
        html += '</div></div>';
    }

    container.innerHTML = html;
}

function renderProspectCard(item, isLarge, colors, badgeClasses) {
    const scoreColor = item.score >= 55 ? 'var(--danger)' : item.score >= 30 ? 'var(--warning)' : 'var(--gray-500)';
    const badgeClass = badgeClasses[item.category] || 'badge-other';
    const priorityBadge = item.priority === 'HIGH' ? '<span class="badge badge-high">High</span>' : item.priority === 'MEDIUM' ? '<span class="badge badge-medium">Medium</span>' : '<span class="badge badge-low">Low</span>';

    const actions = [
        { label: '✉️ Send Note', action: 'connection_sent', cls: 'sent' },
        { label: '🤝 Connected', action: 'connected', cls: 'connected' },
        { label: '🔄 Follow Up', action: 'follow_up', cls: '' },
        { label: '👀 Review', action: 'review', cls: '' },
    ];

    let actionButtons = '';
    actions.forEach(a => {
        actionButtons += `<button class="action-btn ${a.cls}" onclick="markAction(${item._id || item.id}, '${a.action}')">${a.label}</button>`;
    });

    const sizeClass = isLarge ? 'prospect-card' : 'prospect-details';
    const paddingStyle = isLarge ? 'padding: 16px;' : '';

    return `
        <div class="prospect-card" style="cursor: pointer;" onclick="viewPerson(${item.id || item._id})">
            <div class="prospect-header">
                <div>
                    <div class="prospect-name">${escHtml(item.name)} ${priorityBadge}</div>
                    <div class="prospect-title">${escHtml(item.job_title || 'N/A')}</div>
                    <div class="prospect-company">${escHtml(item.company || '')}</div>
                </div>
                <div style="text-align: right;">
                    <div class="score-bar">
                        <span class="score-value" style="color: ${scoreColor};">${item.score}</span>
                        <span class="badge ${badgeClass}">${item.category.replace('_', ' ')}</span>
                    </div>
                </div>
            </div>
            <div style="font-size: 13px; color: var(--gray-500); margin-top: 8px;">
                ${escHtml(item.location || '')} • ${escHtml(item.relationship_type || '')}
            </div>
            <div style="font-size: 13px; color: var(--gray-700); margin-top: 8px;">
                ${escHtml(item.why_relevant || '').substring(0, 100)}...
            </div>
            <div style="display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap;">
                ${actionButtons}
            </div>
            <div style="margin-top: 8px;">
                <button class="action-btn" onclick="event.stopPropagation(); viewPerson(${item.id || item._id})">📋 View Details</button>
            </div>
        </div>
    `;
}

function renderHighRelevance(queueData) {
    const container = document.getElementById('high-relevance-container');
    if (!queueData || !queueData.queue) {
        container.innerHTML = '';
        return;
    }

    const allHigh = [];
    for (const [, items] of Object.entries(queueData.queue)) {
        items.forEach(item => {
            if (item.score >= 40) allHigh.push(item);
        });
    }

    allHigh.sort((a, b) => b.score - a.score);
    const top5 = allHigh.slice(0, 5);

    if (top5.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No high-relevance prospects yet</p></div>';
        return;
    }

    const colors = { CLIENT: '#dbeafe', REFERRAL_PARTNER: '#d1fae5', AGENCY_BUSINESS: '#ede9fe', PROFESSIONAL_NETWORK: '#f3f4f6', OTHER: '#f3f4f6' };
    const badgeClasses = { CLIENT: 'badge-client', REFERRAL_PARTNER: 'badge-referral', AGENCY_BUSINESS: 'badge-agency', PROFESSIONAL_NETWORK: 'badge-professional', OTHER: 'badge-other' };

    let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">';
    top5.forEach(item => {
        html += renderProspectCard(item, false, colors, badgeClasses);
    });
    html += '</div>';
    container.innerHTML = html;
}

// ======== QUEUE ========
async function loadQueue() {
    const target = parseInt(document.getElementById('queue-target-page')?.value || document.getElementById('queue-target')?.value || '20');
    const data = await apiGet(`/queue?target=${target}`);
    if (data) {
        renderQueueFull(data);
    }
}

// ======== PERSON DETAILS ========
async function viewPerson(prospectId) {
    currentPersonId = prospectId;
    const data = await apiGet(`/prospects/${prospectId}`);
    if (!data) return;

    const scoreBreakdown = data.score_breakdown || {};
    const colors = { CLIENT: '#dbeafe', REFERRAL_PARTNER: '#d1fae5', AGENCY_BUSINESS: '#ede9fe', PROFESSIONAL_NETWORK: '#f3f4f6', OTHER: '#f3f4f6' };
    const badgeClasses = { CLIENT: 'badge-client', REFERRAL_PARTNER: 'badge-referral', AGENCY_BUSINESS: 'badge-agency', PROFESSIONAL_NETWORK: 'badge-professional', OTHER: 'badge-other' };

    document.getElementById('person-title').textContent = data.name;

    const scoreItems = Object.entries(scoreBreakdown).map(([key, val]) => {
        const labels = {
            pixel_labs_target: 'Pixel Labs Target',
            founder_decision_maker: 'Founder/Decision Maker',
            referral_potential: 'Referral Potential',
            relevant_industry: 'Relevant Industry',
            relevant_location: 'Relevant Location',
            relevant_role: 'Relevant Role',
            personalization_info: 'Personalization Info',
            professional_network_relevance: 'Network Relevance',
        };
        return `<div class="score-item"><span>${labels[key] || key}</span><span>${val}</span></div>`;
    }).join('');

    const detailItems = `
        <div class="detail-grid">
            <div class="detail-item"><label>Category</label><p><span class="badge ${badgeClasses[data.category] || 'badge-other'}">${data.category.replace('_', ' ')}</span></p></div>
            <div class="detail-item"><label>Score</label><p><strong>${data.score}/100</strong> - ${data.priority} Relevance</p></div>
            <div class="detail-item"><label>Relationship Type</label><p>${data.relationship_type || 'N/A'}</p></div>
            <div class="detail-item"><label>Status</label><p><span class="badge badge-${data.status.toLowerCase()}">${data.status}</span></p></div>
            <div class="detail-item"><label>Location</label><p>${data.location || 'N/A'}</p></div>
            <div class="detail-item"><label>Industry</label><p>${data.industry || 'N/A'}</p></div>
            <div class="detail-item"><label>LinkedIn</label><p>${data.linkedin_url ? `<a href="${data.linkedin_url}" target="_blank">${data.linkedin_url}</a>` : 'N/A'}</p></div>
            <div class="detail-item"><label>Email</label><p>${data.email || 'N/A'}</p></div>
        </div>
    `;

    const scoreBreakdownHtml = `
        <div class="card" style="margin-top: 20px;">
            <div class="card-header"><h2 class="card-title">Score Breakdown</h2></div>
            <div class="score-breakdown">${scoreItems}</div>
        </div>
    `;

    const noteSection = `
        <div class="card" style="margin-top: 20px;">
            <div class="card-header"><h2 class="card-title">Actions & Notes</h2></div>
            <div class="note-box">
                <strong>Connection Suggestion:</strong><br>
                ${data.connection_note || 'Insufficient information for personalization.'}
            </div>
            <div class="note-box" style="margin-top: 12px;">
                <strong>Why Relevant:</strong><br>
                ${data.why_relevant || 'No explanation available.'}
            </div>
            <div class="note-box" style="margin-top: 12px;">
                <strong>Follow-up Topic:</strong><br>
                ${data.follow_up_topic || 'Insufficient information.'}
            </div>
            <div class="form-group" style="margin-top: 16px;">
                <label class="form-label">Mark Status</label>
                <div class="btn-group">
                    <button class="btn btn-success btn-sm" onclick="markAction(${data.id}, 'connection_sent')">✉️ Connection Sent</button>
                    <button class="btn btn-primary btn-sm" onclick="markAction(${data.id}, 'connected')">🤝 Connected</button>
                    <button class="btn btn-warning btn-sm" onclick="markAction(${data.id}, 'follow_up')">🔄 Follow Up</button>
                    <button class="btn btn-outline btn-sm" onclick="markAction(${data.id}, 'review')">👀 Review</button>
                </div>
            </div>
            <div class="form-group" style="margin-top: 12px;">
                <label class="form-label">Add Notes</label>
                <textarea class="form-textarea" id="notes-textarea" placeholder="Add your notes...">${data.notes || ''}</textarea>
                <button class="btn btn-outline btn-sm" onclick="saveNotes(${data.id})" style="margin-top: 8px;">Save Notes</button>
            </div>
        </div>
    `;

    const modal = document.getElementById('person-modal-content');
    modal.innerHTML = `
        <div class="modal-header">
            <h2>${data.name}</h2>
            <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        ${detailItems}
        ${scoreBreakdownHtml}
        ${noteSection}
    `;
    document.getElementById('person-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('person-modal').classList.remove('active');
}

// ======== ACTIONS ========
async function markAction(prospectId, action) {
    const result = await apiPost(`/prospects/${prospectId}/action`, { status: action });
    if (result) {
        showToast(`Action "${action}" recorded for prospect ${prospectId}`, 'success');
        closeModal();
        loadDashboard();
    }
}

async function saveNotes(prospectId) {
    const textarea = document.getElementById('notes-textarea');
    if (!textarea) return;
    const notes = textarea.value;
    const result = await apiPost(`/prospects/${prospectId}/action`, { notes: notes });
    if (result) {
        showToast('Notes saved', 'success');
        closeModal();
    }
}

// ======== IMPORT ========
function handleFileUpload(type) {
    const fileInput = document.getElementById(`${type}-file`);
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const endpoint = type === 'csv' ? '/import/csv' : type === 'xlsx' ? '/import/xlsx' : '/import/json';
    const statusEl = document.getElementById('import-status');

    statusEl.innerHTML = '<div class="spinner" style="margin: 16px auto;"></div><p style="text-align: center;">Importing...</p>';

    apiUpload(endpoint, formData).then(result => {
        if (result && result.success) {
            const importResult = result.import_result;
            statusEl.innerHTML = `
                <div class="card" style="border-color: var(--success);">
                    <h3 style="color: var(--success);">✅ Import Complete</h3>
                    <p>Imported: <strong>${importResult.imported}</strong> prospects</p>
                    <p>Skipped (duplicates): <strong>${importResult.skipped}</strong></p>
                    ${importResult.errors.length > 0 ? `<p style="color: var(--danger);">Errors: ${importResult.errors.length}</p>` : ''}
                </div>
            `;
            showToast(`Imported ${importResult.imported} prospects`, 'success');
        }
    });
}

// Manual add form
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('manual-add-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                name: document.getElementById('manual-name').value,
                job_title: document.getElementById('manual-job_title').value || undefined,
                company: document.getElementById('manual-company').value || undefined,
                location: document.getElementById('manual-location').value || undefined,
                linkedin_url: document.getElementById('manual-linkedin_url').value || undefined,
                industry: document.getElementById('manual-industry').value || undefined,
                bio: document.getElementById('manual-bio').value || undefined,
                notes: document.getElementById('manual-notes').value || undefined,
            };
            const result = await apiPost('/import/manual', data);
            if (result && result.success) {
                showToast(`Prospect "${data.name}" added!`, 'success');
                form.reset();
            } else if (result && !result.success) {
                showToast(result.message, 'error');
            }
        });
    }
});

// ======== HISTORY ========
async function loadHistory() {
    const data = await apiGet('/history/daily');
    if (!data) return;

    document.getElementById('hist-today').textContent = data.total_today || 0;
    document.getElementById('hist-sent-today').textContent = data.connection_sent_or_connected || 0;
    document.getElementById('hist-connected-today').textContent = data.stats?.CONNECTED || 0;
    document.getElementById('hist-total-actions').textContent = data.total_today || 0;

    const history = await apiGet('/history?limit=50');
    if (!history) return;

    const tbody = document.getElementById('activity-tbody');
    if (!history.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--gray-500);">No activity yet</td></tr>';
        return;
    }

    const actionColors = {
        IMPORTED: '#2563eb', IMPORTED: '#2563eb', IMPORTED: '#2563eb',
        CONNECTION_SENT: '#059669', CONNECTED: '#7c3aed',
        FOLLOW_UP: '#d97706', REVIEW: '#6b7280',
        NOT_INTERESTED: '#9ca3af', DO_NOT_CONTACT: '#dc2626',
    };

    tbody.innerHTML = history.map(row => `
        <tr>
            <td>${row.timestamp ? row.timestamp.split('T')[0] : ''}</td>
            <td>${escHtml(row.name)}</td>
            <td>${escHtml(row.company || '')}</td>
            <td><span class="badge" style="background: ${actionColors[row.action] || '#f3f4f6'}; color: ${actionColors[row.action] ? '#fff' : '#374151'};">${row.action}</span></td>
            <td style="font-size: 13px; color: var(--gray-500);">${escHtml(row.details || '')}</td>
        </tr>
    `).join('');
}

// ======== ICP PROFILES ========
async function loadIcp() {
    const icp = await apiGet('/icp');
    const allIcp = await apiGet('/icp/all');
    if (!icp) return;

    const icpEl = document.getElementById('icp-data');
    if (!icpEl) return;

    if (icp.name) {
        icpEl.innerHTML = `
            <div class="form-row" style="margin-bottom: 12px;">
                <div class="form-group">
                    <label class="form-label">Profile Name</label>
                    <input class="form-input" id="icp-name" value="${escHtml(icp.name)}">
                </div>
                <div class="form-group">
                    <label class="form-label">Status</label>
                    <select class="form-select" id="icp-is-active">
                        <option value="1" ${icp.is_active ? 'selected' : ''}>Active</option>
                        <option value="0" ${!icp.is_active ? 'selected' : ''}>Inactive</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Target Industries (comma-separated)</label>
                <input class="form-input" id="icp-industries" value="${(icp.target_industries || []).join(', ')}">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Target Locations</label>
                    <input class="form-input" id="icp-locations" value="${(icp.target_locations || []).join(', ')}">
                </div>
                <div class="form-group">
                    <label class="form-label">Target Job Titles</label>
                    <input class="form-input" id="icp-titles" value="${(icp.target_titles || []).join(', ')}">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Target Keywords</label>
                    <input class="form-input" id="icp-keywords" value="${(icp.target_keywords || []).join(', ')}">
                </div>
                <div class="form-group">
                    <label class="form-label">Exclude Keywords</label>
                    <input class="form-input" id="icp-exclude" value="${(icp.exclude_keywords || []).join(', ')}">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Industry Weight (max ${icp.max_score || 100})</label>
                    <input type="number" class="form-input" id="icp-industry-w" value="${icp.industry_weight}" min="0" max="100">
                </div>
                <div class="form-group">
                    <label class="form-label">Title Weight</label>
                    <input type="number" class="form-input" id="icp-title-w" value="${icp.title_weight}" min="0" max="100">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Location Weight</label>
                    <input type="number" class="form-input" id="icp-location-w" value="${icp.location_weight}" min="0" max="100">
                </div>
                <div class="form-group">
                    <label class="form-label">Company/Keyword Weight</label>
                    <input type="number" class="form-input" id="icp-keyword-w" value="${icp.keyword_weight}" min="0" max="100">
                </div>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary btn-sm" onclick="saveIcp(${icp.id})">💾 Save Profile</button>
                <button class="btn btn-success btn-sm" onclick="scoreAllAgainstIcp()">📊 Score All Prospects</button>
                <button class="btn btn-danger btn-sm" onclick="deleteIcp(${icp.id})">🗑️ Delete</button>
            </div>
            <div id="icp-scores" style="margin-top: 16px;"></div>
        `;
    }
}

async function saveIcp(profileId) {
    const data = {
        name: document.getElementById('icp-name')?.value || 'Default ICP',
        is_active: document.getElementById('icp-is-active')?.value === '1',
        target_industries: document.getElementById('icp-industries')?.value.split(',').map(s => s.trim()).filter(s => s) || [],
        target_locations: document.getElementById('icp-locations')?.value.split(',').map(s => s.trim()).filter(s => s) || [],
        target_titles: document.getElementById('icp-titles')?.value.split(',').map(s => s.trim()).filter(s => s) || [],
        target_keywords: document.getElementById('icp-keywords')?.value.split(',').map(s => s.trim()).filter(s => s) || [],
        exclude_keywords: document.getElementById('icp-exclude')?.value.split(',').map(s => s.trim()).filter(s => s) || [],
        industry_weight: parseInt(document.getElementById('icp-industry-w')?.value) || 25,
        location_weight: parseInt(document.getElementById('icp-location-w')?.value) || 15,
        title_weight: parseInt(document.getElementById('icp-title-w')?.value) || 20,
        keyword_weight: parseInt(document.getElementById('icp-keyword-w')?.value) || 10,
    };
    const result = await apiPut(`/icp/${profileId}`, data);
    if (result) {
        showToast('ICP profile saved!', 'success');
        loadIcp();
    }
}

async function deleteIcp(profileId) {
    const result = await apiDelete(`/icp/${profileId}`);
    if (result) {
        showToast('ICP profile deleted', 'success');
        loadIcp();
    }
}

async function scoreAllAgainstIcp() {
    const result = await apiGet('/icp/batch-score');
    if (result) {
        showToast(`Scored ${result.scored} prospects against ICP!`, 'success');
        const scoresEl = document.getElementById('icp-scores');
        if (scoresEl && result.results) {
            const topMatches = result.results.filter(r => r.meets_icp).sort((a, b) => b.icp_score - a.icp_score).slice(0, 10);
            if (topMatches.length) {
                scoresEl.innerHTML = `<div class="card" style="margin-top: 12px;"><div class="card-header"><h3>Top ICP Matches</h3></div><div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 8px;">${topMatches.map(m => `<div style="padding: 8px; background: var(--gray-50); border-radius: 6px;"><strong>${escHtml(m.name)}</strong> — ICP Score: ${m.icp_score} (${m.meets_icp ? '✅ Match' : '❌ No Match'})</div>`).join('')}</div></div>`;
            }
        }
        loadDashboard();
    }
}

// ======== SETTINGS ========
async function loadSettings() {
    const aiStatus = await apiGet('/ai/status');
    if (aiStatus) {
        const aiEl = document.getElementById('ai-status');
        if (aiStatus.available) {
            aiEl.innerHTML = `
                <p style="color: var(--success);">✅ AI is available</p>
                <p style="font-size: 13px; color: var(--gray-500);">Model: ${aiStatus.model}</p>
            `;
        } else {
            aiEl.innerHTML = `
                <p style="color: var(--warning);">⚠️ AI not configured</p>
                <p style="font-size: 13px; color: var(--gray-500);">Set OPENAI_API_KEY in .env file to enable AI personalization</p>
            `;
        }
    }

    const settings = await apiGet('/settings');
    if (settings) {
        document.getElementById('settings-target').value = settings.daily_target;
    }

    loadIcp();
}

async function saveTarget() {
    const target = document.getElementById('settings-target').value;
    await apiPost('/settings/target', { target });
    showToast(`Daily target set to ${target}`, 'success');
    loadDashboard();
}

// ======== EXPORT ========
async function exportQueue() {
    const data = await apiGet('/export');
    if (data && data.csv_content) {
        const blob = new Blob([data.csv_content], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename || 'linkedin_networking_queue.csv';
        a.click();
        URL.revokeObjectURL(url);
        showToast('CSV exported!', 'success');
    } else {
        showToast('Export failed', 'error');
    }
}

// ======== UTILITIES ========
function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

// Close modal on click outside
document.getElementById('person-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'person-modal') closeModal();
});

// Keyboard shortcut
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});
