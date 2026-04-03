'use strict';

const DATA = '/data_export';

// Ranked by significance (most significant first) — only these appear in Nearby Highlights
const SWISS_TOP20 = [
  "zurich", "geneve", "zermatt", "basel", "luzern",
  "bern", "lausanne", "interlaken", "davos", "st-moritz",
  "grindelwald", "lugano", "lauterbrunnen", "montreux", "ascona",
  "arosa", "pontresina", "vernier", "saanen", "engelberg",
  "locarno", "st-gallen", "laax", "saas-fee", "chur",
  "vaz-obervaz", "winterthur", "leukerbad", "adelboden", "crans-montana",
  "flims"
];

let allPlaces = [];
let coordinates = {};
let detailCache = {};
let currentSearch = '';
let currentCanton = '';
let expandedSlug = null;
let mainMap = null;
let miniMapInstance = null;

// ── Init ────────────────────────────────────────────────────────────────────

async function init() {
  try {
    const [places, coords] = await Promise.all([
      fetch(`${DATA}/places-index.json`).then(r => r.json()),
      fetch(`${DATA}/coordinates.json`).then(r => r.json())
    ]);
    allPlaces = places;
    coordinates = coords;
    renderLeaderboard();
    populateCantonFilter();
    renderList();
    setupEvents();
  } catch (e) {
    console.error('Failed to load data:', e);
    document.getElementById('places-list').innerHTML =
      '<p class="no-results">Could not load ranking data. Please try again.</p>';
  }
}

// ── Leaderboard (hero sidebar) ───────────────────────────────────────────────

function renderLeaderboard() {
  const el = document.getElementById('leaderboard-list');
  if (!el) return;
  el.innerHTML = allPlaces.slice(0, 10).map((p, i) => `
    <div class="lb-item" onclick="jumpToPlace('${p.slug}')">
      <span class="lb-rank">${String(i + 1).padStart(2, '0')}</span>
      <div class="lb-info">
        <span class="lb-name">${p.name}</span>
        <span class="lb-canton">${p.canton}</span>
      </div>
      <span class="lb-score">${Math.round(p.score_total)}</span>
    </div>
  `).join('');
}

function jumpToPlace(slug) {
  currentSearch = '';
  currentCanton = '';
  const si = document.getElementById('search-input');
  const cf = document.getElementById('canton-filter');
  if (si) si.value = '';
  if (cf) cf.value = '';
  switchTab('list');
  expandedSlug = slug;
  renderList();
  setTimeout(() => {
    const card = document.querySelector(`[data-slug="${slug}"]`);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 80);
}

// ── Canton filter ────────────────────────────────────────────────────────────

function populateCantonFilter() {
  const cantons = [...new Set(allPlaces.map(p => p.canton))].sort();
  const sel = document.getElementById('canton-filter');
  if (!sel) return;
  cantons.forEach(c => {
    const o = document.createElement('option');
    o.value = c; o.textContent = c;
    sel.appendChild(o);
  });
}

// ── List rendering ───────────────────────────────────────────────────────────

function getFiltered() {
  const q = currentSearch.toLowerCase();
  return allPlaces.filter(p =>
    p.name.toLowerCase().includes(q) &&
    (!currentCanton || p.canton === currentCanton)
  );
}

function renderList() {
  const container = document.getElementById('places-list');
  if (!container) return;
  const filtered = getFiltered();

  if (filtered.length === 0) {
    container.innerHTML = '<p class="no-results">No destinations match your search.</p>';
    return;
  }

  container.innerHTML = filtered.map(place => {
    const rank = allPlaces.indexOf(place) + 1;
    return renderCard(place, rank, expandedSlug === place.slug);
  }).join('');

  if (expandedSlug) {
    const place = allPlaces.find(p => p.slug === expandedSlug);
    if (place && getFiltered().includes(place)) {
      loadAndRenderDetail(expandedSlug);
    }
  }
}

function renderCard(place, rank, isExpanded) {
  const s = place.scores || {};
  const baseVal  = s.base   != null ? s.base   : (place.subscores?.base_quality  ?? 0);
  const accessVal = s.access != null ? s.access : (place.subscores?.access_value ?? 0);
  return `
    <div class="place-card${isExpanded ? ' expanded' : ''}" data-slug="${place.slug}">
      <div class="card-header" onclick="toggleCard('${place.slug}')">
        <div class="card-left">
          <span class="rank">${String(rank).padStart(2, '0')}</span>
          <div>
            <div class="place-name">${place.name}</div>
            <div class="place-meta">${place.canton}</div>
          </div>
        </div>
        <div class="card-right">
          <span class="total-score">${Math.round(place.score_total)}</span>
          <span class="expand-icon">${isExpanded ? '−' : '+'}</span>
        </div>
      </div>
      <div class="card-bars" onclick="toggleCard('${place.slug}')">
        ${bar('BASE',   baseVal)}
        ${bar('ACCESS', accessVal)}
      </div>
      ${isExpanded ? `<div class="card-detail" id="detail-${place.slug}">
        <div class="detail-loading">Loading…</div>
      </div>` : ''}
    </div>
  `;
}

function bar(label, value) {
  const v = Math.round(value);
  return `
    <div class="bar-row">
      <span class="bar-label">${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${v}%"></div></div>
      <span class="bar-value">${v}</span>
    </div>
  `;
}

// ── Card expand/collapse ─────────────────────────────────────────────────────

async function toggleCard(slug) {
  if (miniMapInstance) {
    miniMapInstance.remove();
    miniMapInstance = null;
  }

  if (expandedSlug === slug) {
    expandedSlug = null;
    renderList();
    return;
  }

  expandedSlug = slug;
  renderList();

  setTimeout(() => {
    const card = document.querySelector(`[data-slug="${slug}"]`);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, 60);
}

async function loadAndRenderDetail(slug) {
  const container = document.getElementById(`detail-${slug}`);
  if (!container) return;

  try {
    if (!detailCache[slug]) {
      detailCache[slug] = await fetch(`${DATA}/places/${slug}.json`).then(r => r.json());
    }
    renderDetail(slug, detailCache[slug], container);
  } catch (e) {
    container.innerHTML = '<div class="detail-loading">Could not load details.</div>';
  }
}

function getPlaceName(slug) {
  const p = allPlaces.find(p => p.slug === slug);
  return p ? p.name : slug;
}

function renderDetail(slug, detail, container) {
  const s = detail.scores || {};
  const sub = s.sub || {};
  const coord = coordinates[slug];

  const gmUrl = coord
    ? `https://www.google.com/maps/search/?api=1&query=${coord.lat},${coord.lon}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(detail.name + ' Switzerland')}`;

  const hotelUrl = 'https://www.swisshotels.com';

  // Grid cell values
  const historicTown = detail.isos_name ? '✓' : '—';

  const reachableSlugs = detail.reachable_slugs || [];
  const highlights = SWISS_TOP20
    .filter(s => reachableSlugs.includes(s))
    .slice(0, 3)
    .map(s => getPlaceName(s))
    .join(' · ');
  const highlightsDisplay = highlights || '—';

  const displayScore = v => v != null ? `${Math.round(v)} / 100` : '—';
  const mtAccess   = displayScore(sub.scenic_transport);
  const cultAccess = displayScore(sub.cultural_access);

  const metricsHtml = `
    <div class="metric-item">
      <span class="metric-label">Historic town</span>
      <span class="metric-value">${historicTown}</span>
    </div>
    <div class="metric-item metric-item--wide">
      <span class="metric-label">Nearby highlights</span>
      <span class="metric-value metric-value--highlights">${highlightsDisplay}</span>
    </div>
    <div class="metric-item">
      <span class="metric-label">Mountain access</span>
      <span class="metric-value">${mtAccess}</span>
    </div>
    <div class="metric-item">
      <span class="metric-label">Culture access</span>
      <span class="metric-value">${cultAccess}</span>
    </div>
  `;

  container.innerHTML = `
    <div class="detail-grid">
      <div class="detail-map-col">
        <div id="mini-map-${slug}" class="mini-map"></div>
      </div>
      <div class="detail-info-col">
        <div class="detail-metrics">${metricsHtml}</div>
        ${renderSeasonality(detail.seasonality)}
        <div class="detail-actions">
          <a href="${hotelUrl}" target="_blank" rel="noopener noreferrer" class="btn-primary">Find a hotel ↗</a>
          <a href="${gmUrl}"    target="_blank" rel="noopener noreferrer" class="btn-secondary">Google Maps ↗</a>
        </div>
      </div>
    </div>
  `;

  if (coord) {
    setTimeout(() => initMiniMap(slug, coord), 80);
  }
}

// ── Seasonality widget ───────────────────────────────────────────────────────

function renderSeasonality(seasonality) {
  if (!seasonality || !Array.isArray(seasonality.monthly_index) || seasonality.monthly_index.length !== 12) {
    return '';
  }

  const { monthly_index } = seasonality;
  const W = 460, H = 52, PX = 6, PY = 6;
  const maxVal = Math.max(...monthly_index);
  const minVal = Math.min(...monthly_index);
  const range = maxVal - minVal || 1;

  const pts = monthly_index.map((val, i) => {
    const x = PX + (i / 11) * (W - PX * 2);
    const y = PY + (1 - (val - minVal) / range) * (H - PY * 2);
    return [x, y];
  });

  const linePoints = pts.map(([x, y]) => `${x},${y}`).join(' ');
  const areaPath = `M ${pts[0][0]},${pts[0][1]} ` +
    pts.slice(1).map(([x, y]) => `L ${x},${y}`).join(' ') +
    ` L ${pts[11][0]},${H} L ${pts[0][0]},${H} Z`;

  const labels = 'JFMAMJJASOND'.split('').map((m, i) => {
    const x = PX + (i / 11) * (W - PX * 2);
    return `<text x="${x}" y="${H + 18}" text-anchor="middle" class="sbar-month-label">${m}</text>`;
  }).join('');

  return `
    <div class="seasonality-widget">
      <svg viewBox="0 0 ${W} ${H + 22}" width="100%" style="overflow:visible;display:block">
        <path d="${areaPath}" fill="#2563EB" fill-opacity="0.08"/>
        <polyline points="${linePoints}" fill="none" stroke="#2563EB" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
        ${labels}
      </svg>
    </div>
  `;
}

// ── Mini map ─────────────────────────────────────────────────────────────────

function initMiniMap(slug, coord) {
  const el = document.getElementById(`mini-map-${slug}`);
  if (!el || miniMapInstance) return;

  miniMapInstance = L.map(el, {
    zoomControl: false,
    attributionControl: false,
    dragging: false,
    scrollWheelZoom: false,
    doubleClickZoom: false
  }).setView([coord.lat, coord.lon], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(miniMapInstance);

  L.circleMarker([coord.lat, coord.lon], {
    radius: 9,
    fillColor: '#2563EB',
    color: '#ffffff',
    weight: 2.5,
    fillOpacity: 1
  }).addTo(miniMapInstance);
}

// ── Main map tab ─────────────────────────────────────────────────────────────

function initMainMap() {
  if (mainMap) return;
  const el = document.getElementById('map');
  if (!el) return;

  mainMap = L.map(el).setView([46.8, 8.2], 8);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mainMap);

  allPlaces.forEach(place => {
    const coord = coordinates[place.slug];
    if (!coord) return;
    const score = Math.round(place.score_total);

    L.circleMarker([coord.lat, coord.lon], {
      radius: 7,
      fillColor: scoreColor(score),
      color: '#ffffff',
      weight: 1.5,
      fillOpacity: 0.92
    }).bindPopup(`
      <strong>${place.name}</strong>
      <span class="popup-canton">${place.canton}</span>
      <span class="popup-score">${score}</span>
      <a class="popup-link" href="#ranking" onclick="jumpToPlace('${place.slug}')">View details →</a>
    `, { maxWidth: 180 }).addTo(mainMap);
  });
}

function scoreColor(score) {
  if (score >= 75) return '#1D4ED8';
  if (score >= 65) return '#3B82F6';
  if (score >= 55) return '#93C5FD';
  return '#CBD5E1';
}

// ── Tab switching ────────────────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-content').forEach(c =>
    c.classList.toggle('active', c.id === `tab-${name}`));

  if (name === 'map') {
    setTimeout(() => {
      initMainMap();
      if (mainMap) mainMap.invalidateSize();
    }, 80);
  }
}

// ── Events ───────────────────────────────────────────────────────────────────

function setupEvents() {
  document.getElementById('search-input')?.addEventListener('input', e => {
    currentSearch = e.target.value;
    expandedSlug = null;
    if (miniMapInstance) { miniMapInstance.remove(); miniMapInstance = null; }
    renderList();
  });

  document.getElementById('canton-filter')?.addEventListener('change', e => {
    currentCanton = e.target.value;
    expandedSlug = null;
    if (miniMapInstance) { miniMapInstance.remove(); miniMapInstance = null; }
    renderList();
  });

  document.querySelectorAll('.tab-btn').forEach(btn =>
    btn.addEventListener('click', () => switchTab(btn.dataset.tab)));
}

// ── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
