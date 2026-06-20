/* ── STATE ─────────────────────────────────────────────────────────────────── */
const S = {
  bank:             'all',
  startDate:        '',
  endDate:          '',
  page:             1,
  perPage:          50,
  showInternal:     false,
  search:           '',
  category:         'all',
  breakdownType:    'income',
  categories:       { income: [], expense: [], all: [], colors: {} },
  summary:          null,
  similarData:      null,
  charts:           { income: null, expense: null },
  trendsChart:      null,
  trendsGranularity:'monthly',
  showNet:          true,
  barChart:         null,
  barGranularity:   'monthly',
  barTab:           'category',
  barCategory:      'all',
  searchTimer:      null,
  sortCol:          null,
  sortDir:          'desc',
};

/* ── BOOT ──────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  await loadCategories();
  const banks = await apiFetchBanks();
  if (banks.length > 0) {
    showDashboard();
    await refresh();
  }
});

async function refresh() {
  await Promise.all([
    loadSummary(),
    loadTransactions(),
    loadBanks(),
    loadMonthOptions(),
    loadInvestments(),
    loadTrends(),
    loadBarChart(),
  ]);
}


/* ── CATEGORIES ────────────────────────────────────────────────────────────── */
async function loadCategories() {
  const d = await api('/api/categories');
  S.categories = d;
  populateCatFilter();
}

function alphaSorted(arr) {
  const others = arr.filter(x => x.startsWith('Other'));
  const rest   = arr.filter(x => !x.startsWith('Other')).sort((a, b) => a.localeCompare(b));
  return [...rest, ...others];
}

function buildOptgroupHTML(selected = null) {
  const c = S.categories;
  const opt = (val, label) =>
    `<option value="${val}"${val === selected ? ' selected' : ''}>${label}</option>`;
  return `
    <optgroup label="Income">
      ${alphaSorted(c.income).map(x => opt(x, x)).join('')}
    </optgroup>
    <optgroup label="Expenses">
      ${alphaSorted(c.expense).map(x => opt(x, x)).join('')}
    </optgroup>
    <optgroup label="Other">
      ${(c.special || ['Internal Transfer', 'Ignore']).map(x => opt(x, x)).join('')}
    </optgroup>`;
}

function populateCatFilter() {
  const sel = document.getElementById('cat-filter');
  sel.innerHTML = '<option value="all">All Categories</option>' + buildOptgroupHTML();
}

/* ── BANKS ─────────────────────────────────────────────────────────────────── */
async function apiFetchBanks() {
  const d = await api('/api/banks');
  return d.banks || [];
}

async function loadBanks() {
  const banks = await apiFetchBanks();
  const el    = document.getElementById('bank-filters');

  el.innerHTML =
    `<button class="bank-btn ${S.bank === 'all' ? 'active' : ''}" onclick="setBank('all')">
       All Banks
     </button>` +
    banks.map(b => {
      const safe = escH(b.bank);
      const js   = escH(b.bank).replace(/'/g, "\\'");
      return `<button class="bank-btn ${S.bank === b.bank ? 'active' : ''}"
                      onclick="setBank('${js}')">
                ${safe}
                <span class="remove-bank" onclick="event.stopPropagation();removeBank('${js}')"
                      title="Remove all ${safe} transactions">✕</span>
              </button>`;
    }).join('');
}

async function removeBank(name) {
  if (!confirm(`Remove all ${name} transactions? This cannot be undone.`)) return;
  await api(`/api/banks/${encodeURIComponent(name)}`, { method: 'DELETE' });
  if (S.bank === name) S.bank = 'all';
  await refresh();
  const banks = await apiFetchBanks();
  if (banks.length === 0) {
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('empty-state').classList.remove('hidden');
  }
}

/* ── SUMMARY + CHARTS ──────────────────────────────────────────────────────── */
async function loadSummary() {
  const d = await api(`/api/summary?${buildParams()}`);
  S.summary = d;
  renderCards(d);
  renderChart('income',  d.income);
  renderChart('expense', d.expenses);
  renderBreakdown();
}

function renderCards(d) {
  document.getElementById('total-income').textContent   = money(d.total_income);
  document.getElementById('total-expenses').textContent = money(d.total_expenses);
  const netEl = document.getElementById('total-net');
  const net   = d.net;
  netEl.textContent = (net >= 0 ? '+' : '−') + money(Math.abs(net));
  netEl.style.color = net >= 0 ? 'var(--income)' : 'var(--expense)';
}

function renderChart(type, items) {
  const wrapId   = type === 'income' ? 'income-chart-wrap' : 'expense-chart-wrap';
  const canvasId = type === 'income' ? 'income-chart'      : 'expense-chart';
  const wrap     = document.getElementById(wrapId);

  if (S.charts[type]) { S.charts[type].destroy(); S.charts[type] = null; }

  if (!items || items.length === 0) {
    wrap.innerHTML = `<div class="chart-empty">No ${type} data for this period</div>`;
    return;
  }

  wrap.innerHTML = `<canvas id="${canvasId}"></canvas>`;
  const ctx      = document.getElementById(canvasId).getContext('2d');
  const total    = items.reduce((s, i) => s + i.total, 0);

  S.charts[type] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels:   items.map(i => i.category),
      datasets: [{
        data:            items.map(i => i.total),
        backgroundColor: items.map(i => i.color),
        borderWidth:     2,
        borderColor:     '#fff',
        hoverOffset:     6,
      }],
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      cutout:              '62%',
      plugins: {
        legend: {
          position: 'right',
          labels: { font: { size: 11 }, boxWidth: 9, padding: 9, color: '#6b7280' },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
              return `  ${money(ctx.raw)}  (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

/* ── BREAKDOWN ─────────────────────────────────────────────────────────────── */
function showBreakdown(type) {
  S.breakdownType = type;
  document.getElementById('tab-income') .classList.toggle('active', type === 'income');
  document.getElementById('tab-expense').classList.toggle('active', type === 'expense');
  renderBreakdown();
}

function renderBreakdown() {
  const data  = S.breakdownType === 'income' ? S.summary?.income : S.summary?.expenses;
  const total = S.breakdownType === 'income' ? S.summary?.total_income : S.summary?.total_expenses;
  const tbody = document.getElementById('breakdown-body');

  if (!data || data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted-lt);padding:24px">
                         No ${S.breakdownType} data</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(item => {
    const pct      = total > 0 ? ((item.total / total) * 100).toFixed(1) : 0;
    const isActive = S.category === item.category;
    const catJs    = item.category.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return `<tr class="bd-row${isActive ? ' bd-active' : ''}"
               onclick="filterToCategory('${catJs}')"
               title="Click to filter transactions by ${escH(item.category)}">
      <td>
        <span class="cat-dot" style="background:${item.color}"></span>
        ${escH(item.category)}
      </td>
      <td class="num">${money(item.total)}</td>
      <td class="bar-cell">
        <span class="pct-text">${pct}%</span>
        <div class="progress">
          <div class="progress-fill" style="width:${pct}%;background:${item.color}"></div>
        </div>
      </td>
      <td class="num" style="color:var(--muted)">${item.count}</td>
    </tr>`;
  }).join('');
}

/* ── TRANSACTIONS ──────────────────────────────────────────────────────────── */
async function loadTransactions() {
  const p = buildParams();
  p.set('page',          S.page);
  p.set('per_page',      S.perPage);
  p.set('show_internal', S.showInternal);
  if (S.search)             p.set('search',   S.search);
  if (S.category !== 'all') p.set('category', S.category);
  if (S.sortCol) {
    p.set('sort_col', S.sortCol);
    p.set('sort_dir', S.sortDir);
  }

  const d = await api(`/api/transactions?${p}`);
  renderTransactions(d.transactions);
  renderPagination(d.total, d.page, d.per_page);
}

function renderTransactions(txns) {
  const tbody = document.getElementById('tx-body');

  if (!txns || txns.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted-lt);padding:32px">
                         No transactions found</td></tr>`;
    return;
  }

  tbody.innerHTML = txns.map(tx => {
    const pos  = tx.amount >= 0;
    const opts = catOptions(tx.category);
    const badge = bankBadge(tx.bank);
    return `<tr>
      <td class="tx-date">${fmtDate(tx.date)}</td>
      <td class="tx-bank">${badge}</td>
      <td class="tx-desc" title="${escH(tx.description)}">${escH(tx.description)}</td>
      <td class="tx-amount ${pos ? 'pos' : 'neg'}">
        ${pos ? '+' : ''}${money(tx.amount)}
      </td>
      <td>
        <select class="cat-select" onchange="updateCat(${tx.id}, this.value)">${opts}</select>
      </td>
      <td>
        <div class="tx-actions">
          <button class="action-btn" onclick="openSimilarModal(${tx.id})">⊕ Similar</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function renderPagination(total, page, perPage) {
  const pages = Math.ceil(total / perPage);
  const el    = document.getElementById('pagination');

  if (pages <= 1) {
    el.innerHTML = `<span>${total} transaction${total !== 1 ? 's' : ''}</span>`;
    return;
  }

  const lo = Math.max(1, page - 2);
  const hi = Math.min(pages, page + 2);

  let html = `<span style="margin-right:8px">${total} transactions</span>`;
  html += `<button class="page-btn" onclick="setPage(${page - 1})" ${page <= 1 ? 'disabled' : ''}>‹</button>`;
  if (lo > 1)   html += `<button class="page-btn" onclick="setPage(1)">1</button>${lo > 2 ? '<span>…</span>' : ''}`;
  for (let i = lo; i <= hi; i++)
    html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="setPage(${i})">${i}</button>`;
  if (hi < pages) html += `${hi < pages - 1 ? '<span>…</span>' : ''}<button class="page-btn" onclick="setPage(${pages})">${pages}</button>`;
  html += `<button class="page-btn" onclick="setPage(${page + 1})" ${page >= pages ? 'disabled' : ''}>›</button>`;

  el.innerHTML = html;
}

/* ── INVESTMENTS ───────────────────────────────────────────────────────────── */
async function loadInvestments() {
  const d   = await api(`/api/investments?${buildParams()}`);
  const card = document.getElementById('invest-card');

  if (!d || d.count === 0) {
    card.classList.add('hidden');
    return;
  }
  card.classList.remove('hidden');

  document.getElementById('invest-platforms').textContent = d.platforms.join(' · ');
  document.getElementById('inv-deposited').textContent = money(d.deposited);
  document.getElementById('inv-withdrawn').textContent = money(d.withdrawn);

  const netEl  = document.getElementById('inv-net');
  const netSub = document.getElementById('inv-net-sub');
  const net    = d.net; // deposited - withdrawn; positive = more in than out
  if (net >= 0) {
    netEl.textContent    = money(net);
    netEl.style.color    = 'var(--primary)';
    netSub.textContent   = 'still in investments';
  } else {
    netEl.textContent    = '−' + money(Math.abs(net));
    netEl.style.color    = 'var(--expense)';
    netSub.textContent   = 'net withdrawn this period';
  }
}

/* ── TRENDS ────────────────────────────────────────────────────────────────── */
async function loadTrends() {
  const p = buildParams();
  p.set('granularity', S.trendsGranularity);
  const d = await api(`/api/trends?${p}`);
  renderTrendsChart(d);
}

function fmtTrendLabel(period, gran) {
  if (gran === 'daily') {
    const [y, m, day] = period.split('-');
    return new Date(+y, +m - 1, +day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
  if (gran === 'weekly') {
    return period.replace('-W', ' W');
  }
  if (gran === 'quarterly') {
    return period.replace('-', ' ');  // "2026-Q1" → "2026 Q1"
  }
  // monthly: "2026-01" → "Jan '26"
  const [y, m] = period.split('-');
  return new Date(+y, +m - 1, 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

function renderTrendsChart(d) {
  const canvas   = document.getElementById('trends-chart');
  const emptyEl  = document.getElementById('trends-empty');
  if (!canvas) return;
  if (S.trendsChart) { S.trendsChart.destroy(); S.trendsChart = null; }

  if (!d.periods || d.periods.length === 0) {
    canvas.style.display = 'none';
    emptyEl.classList.remove('hidden');
    return;
  }
  canvas.style.display = '';
  emptyEl.classList.add('hidden');

  const labels  = d.periods.map(p => fmtTrendLabel(p, S.trendsGranularity));
  const net     = d.income.map((inc, i) => +(inc - d.expenses[i]).toFixed(2));
  const datasets = [
    {
      label: 'Income',
      data: d.income,
      borderColor: '#059669',
      backgroundColor: 'rgba(5,150,105,0.07)',
      fill: true,
      tension: 0.35,
      pointRadius: d.periods.length > 24 ? 0 : 3,
      pointHoverRadius: 5,
      borderWidth: 2,
    },
    {
      label: 'Expenses',
      data: d.expenses,
      borderColor: '#dc2626',
      backgroundColor: 'rgba(220,38,38,0.07)',
      fill: true,
      tension: 0.35,
      pointRadius: d.periods.length > 24 ? 0 : 3,
      pointHoverRadius: 5,
      borderWidth: 2,
    },
  ];
  if (S.showNet) {
    datasets.push({
      label: 'Net',
      data: net,
      borderColor: '#6b7280',
      backgroundColor: 'transparent',
      fill: false,
      tension: 0.35,
      pointRadius: d.periods.length > 24 ? 0 : 3,
      pointHoverRadius: 5,
      borderWidth: 1.5,
      borderDash: [5, 4],
    });
  }

  S.trendsChart = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: c => ` ${c.dataset.label}: $${Math.abs(c.parsed.y).toLocaleString('en-US', { minimumFractionDigits: 2 })}${c.parsed.y < 0 ? ' (deficit)' : ''}`,
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { family: "'DM Sans', sans-serif", size: 12 }, color: '#9ca3af', maxRotation: 45 } },
        y: { grid: { color: '#f0f2f5' }, ticks: { font: { family: "'DM Sans', sans-serif", size: 12 }, color: '#9ca3af', callback: v => '$' + v.toLocaleString('en-US') } },
      },
    },
  });
}

function setGranularity(gran) {
  S.trendsGranularity = gran;
  // Update button states
  document.querySelectorAll('.gran-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.gran === gran);
  });
  loadTrends();
}

function toggleNet() {
  S.showNet = !S.showNet;
  const btn = document.getElementById('net-toggle-btn');
  btn.classList.toggle('active', S.showNet);
  loadTrends();
}

/* ── BAR CHART ─────────────────────────────────────────────────────────────── */
function populateBarCatFilter() {
  const sel = document.getElementById('bar-cat-filter');
  if (!sel) return;
  sel.innerHTML = '<option value="all">All Categories</option>' + buildOptgroupHTML(S.barCategory);
  sel.value = S.barCategory;
}

async function loadBarChart() {
  populateBarCatFilter();
  const p = buildParams();
  p.set('granularity', S.barGranularity);
  if (S.barCategory !== 'all') p.set('category', S.barCategory);
  const d = await api(`/api/bar-trends?${p}`);
  renderBarChart(d);
}

function renderBarChart(d) {
  const canvas  = document.getElementById('bar-chart');
  const emptyEl = document.getElementById('bar-empty');
  if (!canvas) return;
  if (S.barChart) { S.barChart.destroy(); S.barChart = null; }

  if (!d.periods || d.periods.length === 0) {
    canvas.style.display = 'none';
    emptyEl.classList.remove('hidden');
    return;
  }
  canvas.style.display = '';
  emptyEl.classList.add('hidden');

  const labels = d.periods.map(p => fmtTrendLabel(p, S.barGranularity));
  let datasets;

  if (S.barTab === 'vs') {
    // Income vs Expenses — grouped side by side
    datasets = [
      {
        label: 'Income',
        data: d.income,
        backgroundColor: 'rgba(5,150,105,0.75)',
        borderColor: '#059669',
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: 'Expenses',
        data: d.expenses,
        backgroundColor: 'rgba(220,38,38,0.75)',
        borderColor: '#dc2626',
        borderWidth: 1,
        borderRadius: 3,
      },
    ];
  } else {
    // Stacked expenses by category
    const colors = S.categories.colors || {};
    datasets = Object.entries(d.by_category)
      .map(([cat, vals]) => ({
        label: cat,
        data: vals,
        backgroundColor: colors[cat] || '#9ca3af',
        borderColor: 'transparent',
        borderWidth: 0,
        borderRadius: 2,
        stack: 'expenses',
      }));
  }

  S.barChart = new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: S.barTab === 'category' && Object.keys(d.by_category).length <= 8,
          position: 'right',
          labels: { font: { family: "'DM Sans', sans-serif", size: 11 }, boxWidth: 10, padding: 10 },
        },
        tooltip: {
          callbacks: {
            label: c => ` ${c.dataset.label}: $${c.parsed.y.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
          },
        },
      },
      scales: {
        x: { grid: { display: false }, stacked: S.barTab === 'category', ticks: { font: { family: "'DM Sans', sans-serif", size: 12 }, color: '#9ca3af', maxRotation: 45 } },
        y: { grid: { color: '#f0f2f5' }, stacked: S.barTab === 'category', ticks: { font: { family: "'DM Sans', sans-serif", size: 12 }, color: '#9ca3af', callback: v => '$' + v.toLocaleString('en-US') } },
      },
    },
  });
}

function setBarTab(tab) {
  S.barTab = tab;
  document.getElementById('bar-tab-cat').classList.toggle('active', tab === 'category');
  document.getElementById('bar-tab-vs').classList.toggle('active', tab === 'vs');
  loadBarChart();
}

function setBarGranularity(gran) {
  S.barGranularity = gran;
  document.querySelectorAll('.bar-gran-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.gran === gran);
  });
  loadBarChart();
}

function setBarCategory(val) {
  S.barCategory = val;
  loadBarChart();
}

async function loadMonthOptions() {
  const d = await api('/api/date-range');
  if (!d.min || !d.max) return;

  const months = [];
  let cur = new Date(d.min + 'T00:00:00');
  const mx  = new Date(d.max + 'T00:00:00');

  while (cur <= mx) {
    const ym    = cur.toISOString().slice(0, 7);
    const label = cur.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    months.push({ ym, label });
    cur.setMonth(cur.getMonth() + 1);
  }

  const sel = document.getElementById('month-select');
  const prev = sel.value;
  sel.innerHTML = '<option value="">Month…</option>' +
    months.reverse().map(m => `<option value="${m.ym}">${m.label}</option>`).join('');
  if (prev) sel.value = prev;
}

/* ── FILTER ACTIONS ────────────────────────────────────────────────────────── */
function setBank(bank) {
  S.bank = bank; S.page = 1;
  loadBanks();   // re-render buttons immediately
  refresh();
}

function setPreset(preset) {
  const now  = new Date();
  const y    = now.getFullYear();
  document.querySelectorAll('.preset').forEach(b =>
    b.classList.toggle('active', b.dataset.p === preset));
  document.getElementById('month-select').value = '';

  const ranges = {
    all: ['', ''],
    ytd: [`${y}-01-01`, isoDate(now)],
    q1:  [`${y}-01-01`, `${y}-03-31`],
    q2:  [`${y}-04-01`, `${y}-06-30`],
    q3:  [`${y}-07-01`, `${y}-09-30`],
    q4:  [`${y}-10-01`, `${y}-12-31`],
  };
  const [s, e] = ranges[preset] || ['', ''];
  setRange(s, e);
}

function setMonth(ym) {
  if (!ym) return;
  document.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
  const [y, m] = ym.split('-').map(Number);
  const last   = new Date(y, m, 0).getDate();
  setRange(`${ym}-01`, `${ym}-${String(last).padStart(2, '0')}`);
}

function setCustomDate() {
  document.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
  document.getElementById('month-select').value = '';
  setRange(
    document.getElementById('start-date').value,
    document.getElementById('end-date').value,
  );
}

function setRange(start, end) {
  S.startDate = start; S.endDate = end; S.page = 1;
  document.getElementById('start-date').value = start;
  document.getElementById('end-date').value   = end;
  refresh();
}

function toggleInternal() {
  S.showInternal = document.getElementById('show-internal').checked;
  S.page = 1;
  refresh();
}

function setPage(p) { S.page = p; loadTransactions(); }

function debounceSearch() {
  clearTimeout(S.searchTimer);
  S.searchTimer = setTimeout(() => {
    S.search = document.getElementById('tx-search').value.trim();
    S.page   = 1;
    loadTransactions();
  }, 280);
}

function filterCat() {
  S.category = document.getElementById('cat-filter').value;
  S.page     = 1;
  loadTransactions();
  renderBreakdown(); // update active highlight
}

function filterToCategory(cat) {
  // Toggle: clicking the active category clears the filter
  S.category = (S.category === cat) ? 'all' : cat;
  S.page     = 1;
  document.getElementById('cat-filter').value = S.category;
  loadTransactions();
  renderBreakdown(); // update active row highlight
  document.querySelector('.tx-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function updateCat(id, cat) {
  await api(`/api/transaction/${id}`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ category: cat }),
  });
  loadSummary(); // refresh charts + breakdown without reloading table
}

/* ── SIMILAR MODAL ─────────────────────────────────────────────────────────── */
async function openSimilarModal(id) {
  const d      = await api(`/api/similar/${id}`);
  S.similarData = d;

  document.getElementById('sim-pattern').textContent = d.pattern;

  const all  = [d.current, ...d.similar];
  const list = document.getElementById('sim-list');

  list.innerHTML = all.map((tx, i) => `
    <div class="sim-item">
      <input type="checkbox" id="sc-${tx.id}" value="${tx.id}" checked />
      <label for="sc-${tx.id}">
        <div>${escH(tx.description)}</div>
        <div class="sim-meta">
          ${fmtDate(tx.date)} · ${escH(tx.bank)} ·
          <strong>${tx.amount >= 0 ? '+' : ''}${money(tx.amount)}</strong>
          · currently: ${escH(tx.category)}
        </div>
      </label>
    </div>`).join('');

  // Category select — default to current tx's category
  const catSel = document.getElementById('sim-cat');
  catSel.innerHTML = buildOptgroupHTML(d.current.category);

  openModal('similar-modal');
}

async function applyMass() {
  const cat     = document.getElementById('sim-cat').value;
  const save    = document.getElementById('save-rule').checked;
  const ids     = [...document.querySelectorAll('#sim-list input:checked')]
                    .map(cb => parseInt(cb.value));

  if (!ids.length) return;

  await api('/api/mass-categorize', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      transaction_ids: ids,
      category:        cat,
      pattern:         S.similarData?.pattern || '',
      save_rule:       save,
    }),
  });

  closeSimilarModal();
  await refresh();
}

function closeSimilarModal() { closeModal('similar-modal'); }

/* ── UPLOAD MODAL ──────────────────────────────────────────────────────────── */
function openUploadModal() {
  document.getElementById('upload-results').innerHTML = '';
  openModal('upload-modal');
}

function closeUploadModal() {
  closeModal('upload-modal');
  refresh();
}

function handleDragOver(e)  { e.preventDefault(); document.getElementById('drop-zone').classList.add('drag-over'); }
function handleDragLeave()  { document.getElementById('drop-zone').classList.remove('drag-over'); }
function handleDrop(e)      { e.preventDefault(); handleDragLeave(); uploadFiles([...e.dataTransfer.files].filter(f => f.name.endsWith('.csv'))); }
function handleFileSelect(e){ uploadFiles([...e.target.files]); e.target.value = ''; }

async function uploadFiles(files) {
  if (!files.length) return;

  const resultsEl = document.getElementById('upload-results');
  resultsEl.innerHTML = '<p style="color:var(--muted);padding:10px 0">Uploading…</p>';

  const form = new FormData();
  files.forEach(f => form.append('files', f));

  try {
    const d = await api('/api/upload', { method: 'POST', body: form });

    resultsEl.innerHTML = d.results.map(r => {
      if (r.error) return `
        <div class="upload-result">
          <span class="result-icon">✗</span>
          <div><div>${escH(r.file)}</div><div class="result-error">${escH(r.error)}</div></div>
        </div>`;
      return `
        <div class="upload-result">
          <span class="result-icon">✓</span>
          <div><div>${escH(r.file)}</div>
          <div class="result-bank">${escH(r.bank)} · ${r.added} added · ${r.skipped} skipped (duplicates)</div>
          </div>
        </div>`;
    }).join('');

    showDashboard();
    await new Promise(r => requestAnimationFrame(r));
    await refresh();
  } catch (err) {
    resultsEl.innerHTML = `<p style="color:var(--expense)">Upload failed: ${err.message}</p>`;
  }
}


/* ── RULES MODAL ───────────────────────────────────────────────────────────── */
async function openRulesModal() {
  try {
    await loadRules();
    openModal('rules-modal');
  } catch(e) {
    console.error('Rules modal error:', e);
  }
}
function closeRulesModal() { closeModal('rules-modal'); }

async function loadRules() {
  const d     = await api('/api/rules');
  const tbody = document.getElementById('rules-body');

  if (!d.rules || d.rules.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--muted-lt);padding:24px;line-height:1.8">
      No saved rules yet.<br>
      <span style="font-size:12px">Hover any transaction, click <strong>⊕ Similar</strong>,
      then check <strong>"Remember this rule"</strong> when applying a category.</span>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = d.rules.map(r => `
    <tr>
      <td><code style="font-size:12px;color:var(--primary)">${escH(r.pattern)}</code></td>
      <td>${escH(r.category)}</td>
      <td><button class="delete-rule" onclick="deleteRule(${r.id})">✕</button></td>
    </tr>`).join('');
}

async function deleteRule(id) {
  await api(`/api/rules/${id}`, { method: 'DELETE' });
  loadRules();
}

/* ── MODAL HELPERS ─────────────────────────────────────────────────────────── */
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
  document.getElementById('overlay').classList.remove('hidden');
}
function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
  // Only hide overlay if no other modals open
  const open = document.querySelectorAll('.modal:not(.hidden)');
  if (open.length === 0) document.getElementById('overlay').classList.add('hidden');
}
function closeAllModals() {
  document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
  document.getElementById('overlay').classList.add('hidden');
}

/* ── UI HELPERS ────────────────────────────────────────────────────────────── */
function showDashboard() {
  document.getElementById('empty-state').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('hidden');
}

function bankBadge(bank) {
  if (bank === 'Chase')              return `<span class="badge badge-chase">Chase</span>`;
  if (bank === 'Chase CC')           return `<span class="badge badge-chase-cc">Chase CC</span>`;
  if (bank === 'Bank of America')    return `<span class="badge badge-bofa">BofA</span>`;
  if (bank === 'Bank of America CC') return `<span class="badge badge-bofa-cc">BofA CC</span>`;
  return `<span class="badge badge-other">${escH(bank)}</span>`;
}

/* ── SORTING ───────────────────────────────────────────────────────────────── */
function setSort(col) {
  if (col === 'date') {
    // 2-state toggle: asc (oldest) ↔ desc (newest)
    if (S.sortCol !== 'date') {
      S.sortCol = 'date';
      S.sortDir = 'asc';  // first click = oldest to newest
    } else {
      S.sortDir = S.sortDir === 'asc' ? 'desc' : 'asc';
    }
  } else if (col === 'amount') {
    // 3-state: null → desc (highest) → asc (lowest) → null (back to normal)
    if (S.sortCol !== 'amount') {
      S.sortCol = 'amount';
      S.sortDir = 'desc';  // first click = highest to lowest
    } else if (S.sortDir === 'desc') {
      S.sortDir = 'asc';   // second click = lowest to highest
    } else {
      S.sortCol = null;    // third click = back to normal
      S.sortDir = 'desc';
    }
  }
  S.page = 1;
  updateSortHeaders();
  loadTransactions();
}

function updateSortHeaders() {
  const dateIcon   = document.getElementById('sort-icon-date');
  const amountIcon = document.getElementById('sort-icon-amount');
  if (!dateIcon || !amountIcon) return;

  // Reset both
  dateIcon.textContent   = '⇅';
  dateIcon.style.color   = '';
  amountIcon.textContent = '⇅';
  amountIcon.style.color = '';

  if (S.sortCol === 'date') {
    dateIcon.textContent = S.sortDir === 'asc' ? '↑' : '↓';
    dateIcon.style.color = 'var(--primary)';
  } else if (S.sortCol === 'amount') {
    amountIcon.textContent = S.sortDir === 'asc' ? '↑' : '↓';
    amountIcon.style.color = 'var(--primary)';
  }
}

function catOptions(selected) {
  return buildOptgroupHTML(selected);
}

/* ── API HELPER ────────────────────────────────────────────────────────────── */
async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ── PARAM BUILDER ─────────────────────────────────────────────────────────── */
function buildParams() {
  const p = new URLSearchParams();
  if (S.bank !== 'all') p.set('bank',       S.bank);
  if (S.startDate)      p.set('start_date', S.startDate);
  if (S.endDate)        p.set('end_date',   S.endDate);
  return p;
}

/* ── FORMATTERS ────────────────────────────────────────────────────────────── */
function money(n) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
    .format(Math.abs(n));
}

function fmtDate(s) {
  if (!s) return '';
  return new Date(s + 'T00:00:00').toLocaleDateString('en-US',
    { month: 'short', day: 'numeric', year: 'numeric' });
}

function isoDate(d) { return d.toISOString().slice(0, 10); }

function escH(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
