(function () {
  'use strict';

  const API_URL = '/api/user/contributions';
  const pageSize = 10;

  const elems = {
    total: document.getElementById('total-contributions'),
    campaigns: document.getElementById('campaigns-count'),
    first: document.getElementById('first-contribution'),
    recent: document.getElementById('recent-contribution'),
    filterCampaign: document.getElementById('filter-campaign'),
    filterCountry: document.getElementById('filter-country'),
    filterLang: document.getElementById('filter-lang'),
    filterEditType: document.getElementById('filter-edit-type'),
    filterFrom: document.getElementById('filter-date-from'),
    filterTo: document.getElementById('filter-date-to'),
    filterSearch: document.getElementById('filter-search'),
    resetBtn: document.getElementById('btn-reset'),
    state: document.getElementById('mc-state'),
    tbody: document.getElementById('contrib-tbody'),
    pagination: document.getElementById('mc-pagination')
  };

  let chartTime, chartCampaign, chartEditType;
  let allData = [];
  let filtered = [];
  let currentPage = 1;
  let sortKey = 'date';
  let sortDir = -1;

  function chartOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' }
      },
      scales: {
        y: { beginAtZero: true }
      }
    };
  }

  function fetchContributions() {
    showLoading();
    fetch(API_URL)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => init(d.data || d))
      .catch(() => init(mockData()));
  }

  function init(data) {
    allData = data;
    initFilters();
    applyFilters();
    hideLoading();
  }

  function applyFilters() {
    const search = elems.filterSearch.value.toLowerCase();

    filtered = allData.filter(d => {
      if (elems.filterCampaign.value && d.campaign !== elems.filterCampaign.value) return false;
      if (elems.filterCountry.value && d.country !== elems.filterCountry.value) return false;
      if (elems.filterLang.value && d.lang !== elems.filterLang.value) return false;
      if (elems.filterEditType.value && d.edit_type !== elems.filterEditType.value) return false;
      if (search && !d.file.toLowerCase().includes(search)) return false;
      return true;
    });

    updateSummary();
    updateCharts();
    currentPage = 1;
    renderTable();
  }

  function updateCharts() {
    destroyCharts();

    chartTime = new Chart(document.getElementById('chart-time'), {
      type: 'line',
      data: buildTimeData(),
      options: chartOptions()
    });

    chartCampaign = new Chart(document.getElementById('chart-campaign'), {
      type: 'doughnut',
      data: buildCountData('campaign'),
      options: chartOptions()
    });

    chartEditType = new Chart(document.getElementById('chart-edit-type'), {
      type: 'bar',
      data: buildCountData('edit_type'),
      options: chartOptions()
    });
  }

  function destroyCharts() {
    [chartTime, chartCampaign, chartEditType].forEach(c => c && c.destroy());
  }

  function buildTimeData() {
    const map = {};
    filtered.forEach(d => {
      const m = d.date.slice(0, 7);
      map[m] = (map[m] || 0) + 1;
    });
    return {
      labels: Object.keys(map),
      datasets: [{ label: 'Contributions', data: Object.values(map) }]
    };
  }

  function buildCountData(key) {
    const map = {};
    filtered.forEach(d => map[d[key]] = (map[d[key]] || 0) + 1);
    return {
      labels: Object.keys(map),
      datasets: [{ data: Object.values(map) }]
    };
  }

  function updateSummary() {
    elems.total.textContent = filtered.length;
    elems.campaigns.textContent = new Set(filtered.map(d => d.campaign)).size;
    const dates = filtered.map(d => d.date).sort();
    elems.first.textContent = dates[0] || '—';
    elems.recent.textContent = dates[dates.length - 1] || '—';
  }

  function renderTable() {
    elems.tbody.innerHTML = '';
    if (!filtered.length) {
      elems.state.textContent = 'No contributions found';
      return;
    }
    elems.state.textContent = '';

    filtered
      .slice((currentPage - 1) * pageSize, currentPage * pageSize)
      .forEach(d => {
        elems.tbody.insertAdjacentHTML(
          'beforeend',
          `<tr>
            <td>${d.date}</td>
            <td>${d.campaign}</td>
            <td>${d.file}</td>
            <td>${d.edit_type}</td>
            <td>${d.country}</td>
            <td>${d.lang}</td>
          </tr>`
        );
      });
  }

  function showLoading() {
    elems.state.textContent = 'Loading…';
  }

  function hideLoading() {
    elems.state.textContent = '';
  }

  function initFilters() {
    attachEvents();
  }

  function attachEvents() {
    document.querySelectorAll('.mc-filter-input').forEach(el =>
      el.addEventListener('change', applyFilters)
    );
    elems.filterSearch.addEventListener('input', debounce(applyFilters, 300));
    elems.resetBtn.addEventListener('click', () => {
      document.querySelectorAll('.mc-filter-input').forEach(i => i.value = '');
      applyFilters();
    });
  }

  function debounce(fn, wait) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function mockData() {
    return Array.from({ length: 100 }, (_, i) => ({
      date: `2024-0${(i % 9) + 1}-01`,
      campaign: ['Birds', 'Nature'][i % 2],
      file: `File_${i}.jpg`,
      edit_type: ['caption', 'rotate'][i % 2],
      country: 'US',
      lang: 'en'
    }));
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', fetchContributions)
    : fetchContributions();
})();
