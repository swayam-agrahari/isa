(function () {
  'use strict';

  const API_URL = '/api/user/contributions';
  const CAMPAIGNS_API = '/api/campaigns?length=200&start=0&order_col=0&order_dir=asc';
  const pageSize = 10;
  
  // GitHub-style grid configuration
  const DAYS = ['Mon', 'Wed', 'Fri']; // Only show these days like GitHub
  const MONTHS = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];

  const elems = {
    total: document.getElementById('total-contributions'),
    campaigns: document.getElementById('campaigns-count'),
    first: document.getElementById('first-contribution'),
    recent: document.getElementById('recent-contribution'),
    filterCampaign: document.getElementById('filter-campaign'),
    filterLang: document.getElementById('filter-lang'),
    filterEditType: document.getElementById('filter-edit-type'),
    filterFrom: document.getElementById('filter-date-from'),
    filterTo: document.getElementById('filter-date-to'),
    filterSearch: document.getElementById('filter-search'),
    resetBtn: document.getElementById('btn-reset'),
    state: document.getElementById('mc-state'),
    tbody: document.getElementById('contrib-tbody'),
    pagination: document.getElementById('mc-pagination'),
    
    // Grid elements
    monthLabels: document.getElementById('month-labels'),
    dayLabels: document.getElementById('day-labels'),
    yearLabels: document.getElementById('year-labels'),
    weekColumns: document.getElementById('week-columns'),
    tooltip: document.getElementById('contrib-tooltip'),
    prevYearBtn: document.getElementById('prev-year'),
    nextYearBtn: document.getElementById('next-year'),
    resetViewBtn: document.getElementById('reset-view'),
    currentYearDisplay: document.getElementById('current-year-display'),
    contribTotalDisplay: document.getElementById('contrib-total-display')
  };

  let chartTime, chartCampaign, chartEditType;
  let allData = [];
  let filtered = [];
  let currentPage = 1;
  let sortKey = 'date';
  let sortDir = -1;
  
  // Grid state
  let currentYear = new Date().getFullYear();
  let contributionsByDate = new Map();
  let allContributionsByDate = new Map();

  function fetchCampaignOptions() {
    if (!elems.filterCampaign) return;

    fetch(CAMPAIGNS_API)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(payload => {
        const rows = payload && payload.data ? payload.data : [];
        const names = rows
          .map(row => extractCampaignName(row.campaign_html))
          .filter(Boolean);
        populateCampaignSelect([...new Set(names)].sort());
      })
      .catch(() => {
        populateCampaignSelect([]);
      });
  }

  function extractCampaignName(html) {
    if (!html) return '';
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const strong = tmp.querySelector('strong');
    const text = strong ? strong.textContent : tmp.textContent;
    return (text || '').trim();
  }

  function populateCampaignSelect(names) {
    const select = elems.filterCampaign;
    if (!select) return;

    select.innerHTML = '';
    const anyOpt = document.createElement('option');
    anyOpt.value = '';
    anyOpt.textContent = 'Any';
    select.appendChild(anyOpt);

    names.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    });
  }

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
    processAllContributionsData(data);
    populateLanguageSelect(allData);
    initFilters();
    applyFilters();
    hideLoading();
  }

  function processAllContributionsData(data) {
    allContributionsByDate.clear();
    
    data.forEach(contrib => {
      const dateStr = contrib.date;
      if (!dateStr) return;
      
      const date = new Date(dateStr);
      const normalizedDate = date.toISOString().split('T')[0];
      
      if (allContributionsByDate.has(normalizedDate)) {
        allContributionsByDate.set(normalizedDate, allContributionsByDate.get(normalizedDate) + 1);
      } else {
        allContributionsByDate.set(normalizedDate, 1);
      }
    });
    
    updateContributionsGrid();
  }

  function processContributionsData(data) {
    contributionsByDate.clear();
    
    data.forEach(contrib => {
      const dateStr = contrib.date;
      if (!dateStr) return;
      
      const date = new Date(dateStr);
      const normalizedDate = date.toISOString().split('T')[0];
      
      if (contributionsByDate.has(normalizedDate)) {
        contributionsByDate.set(normalizedDate, contributionsByDate.get(normalizedDate) + 1);
      } else {
        contributionsByDate.set(normalizedDate, 1);
      }
    });
    
    updateContributionsGrid();
  }

  function updateContributionsGrid() {
    if (!elems.weekColumns) return;
    
    // Clear existing content
    elems.monthLabels.innerHTML = '';
    elems.dayLabels.innerHTML = '';
    elems.yearLabels.innerHTML = '';
    elems.weekColumns.innerHTML = '';
    
    // Create day labels (only Mon, Wed, Fri like GitHub)
    DAYS.forEach(day => {
      const dayLabel = document.createElement('div');
      dayLabel.className = 'day-label';
      dayLabel.textContent = day;
      elems.dayLabels.appendChild(dayLabel);
    });
    
    // Get contributions for the last year from current date
    const endDate = new Date(currentYear, 11, 31); // Dec 31 of current year
    const startDate = new Date(endDate);
    startDate.setFullYear(startDate.getFullYear() - 1);
    startDate.setDate(startDate.getDate() + 1); // Start from Jan 1 of previous year
    
    // Generate weeks (53 weeks like GitHub)
    const weeks = generateWeeks(startDate, endDate);
    
    // Calculate month positions
    const monthPositions = calculateMonthPositions(weeks);
    
    // Create month labels
    monthPositions.forEach(({ month, startWeek, endWeek }) => {
      const monthLabel = document.createElement('div');
      monthLabel.className = 'month-label';
      monthLabel.textContent = month;
      monthLabel.style.gridColumn = `${startWeek + 1} / ${endWeek + 1}`;
      elems.monthLabels.appendChild(monthLabel);
    });
    
    // Create year labels (on the left side)
    const years = Array.from({ length: 7 }, (_, i) => currentYear - i);
    years.forEach(year => {
      const yearLabel = document.createElement('div');
      yearLabel.className = 'year-label';
      yearLabel.textContent = year;
      elems.yearLabels.appendChild(yearLabel);
    });
    
    // Create week columns
    weeks.forEach((week, weekIndex) => {
      const weekColumn = document.createElement('div');
      weekColumn.className = 'week-column';
      
      // Create 7 days for each week
      week.days.forEach((day, dayIndex) => {
        const dayCell = document.createElement('div');
        dayCell.className = 'day-cell';
        
        // Set contribution level
        const count = day.count || 0;
        let level = 0;
        if (count >= 10) level = 4;
        else if (count >= 5) level = 3;
        else if (count >= 3) level = 2;
        else if (count >= 1) level = 1;
        
        dayCell.classList.add(`level-${level}`);
        
        // Add tooltip data
        if (count > 0 && day.date) {
          const dateStr = day.date.toISOString().split('T')[0];
          dayCell.dataset.date = dateStr;
          dayCell.dataset.count = count;
          const formattedDate = formatDateForTooltip(day.date);
          dayCell.dataset.tooltip = `<strong>${count} contribution${count !== 1 ? 's' : ''}</strong> on ${formattedDate}`;
        }
        
        // Add event listeners
        dayCell.addEventListener('mouseenter', handleDayHover);
        dayCell.addEventListener('mouseleave', handleDayLeave);
        dayCell.addEventListener('click', handleDayClick);
        
        weekColumn.appendChild(dayCell);
      });
      
      elems.weekColumns.appendChild(weekColumn);
    });
    
    // Update displays
    elems.currentYearDisplay.textContent = currentYear;
    
    // Calculate total contributions for the last year
    let yearTotal = 0;
    contributionsByDate.forEach((count, dateStr) => {
      const date = new Date(dateStr);
      if (date >= startDate && date <= endDate) {
        yearTotal += count;
      }
    });
    elems.contribTotalDisplay.textContent = `${yearTotal} contributions`;
  }

  function generateWeeks(startDate, endDate) {
    const weeks = [];
    const currentWeek = new Date(startDate);
    
    // Start from Sunday of the week containing startDate
    currentWeek.setDate(currentWeek.getDate() - currentWeek.getDay());
    
    // Generate 53 weeks (like GitHub)
    for (let week = 0; week < 53; week++) {
      const weekData = {
        days: []
      };
      
      // Generate 7 days for each week (Sunday to Saturday)
      for (let day = 0; day < 7; day++) {
        const currentDay = new Date(currentWeek);
        currentDay.setDate(currentWeek.getDate() + day);
        
        // Check if day is within our date range
        if (currentDay >= startDate && currentDay <= endDate) {
          const dateStr = currentDay.toISOString().split('T')[0];
          const count = contributionsByDate.get(dateStr) || 0;
          
          weekData.days.push({
            date: new Date(currentDay),
            count: count
          });
        } else {
          weekData.days.push({ date: null, count: 0 });
        }
      }
      
      weeks.push(weekData);
      currentWeek.setDate(currentWeek.getDate() + 7);
    }
    
    return weeks;
  }

  function calculateMonthPositions(weeks) {
    const monthPositions = [];
    let currentMonth = null;
    let startWeek = 0;
    
    weeks.forEach((week, weekIndex) => {
      // Find the first valid day in the week
      const validDay = week.days.find(day => day.date);
      if (validDay && validDay.date) {
        const month = MONTHS[validDay.date.getMonth()];
        
        if (currentMonth !== month) {
          if (currentMonth !== null) {
            monthPositions.push({
              month: currentMonth,
              startWeek: startWeek,
              endWeek: weekIndex
            });
          }
          currentMonth = month;
          startWeek = weekIndex;
        }
      }
    });
    
    // Add the last month
    if (currentMonth !== null) {
      monthPositions.push({
        month: currentMonth,
        startWeek: startWeek,
        endWeek: weeks.length
      });
    }
    
    return monthPositions;
  }

  function formatDateForTooltip(date) {
    const options = { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    };
    return date.toLocaleDateString('en-US', options);
  }

  function handleDayHover(event) {
    const dayCell = event.target;
    const tooltip = elems.tooltip;
    const count = dayCell.dataset.count;
    const tooltipHtml = dayCell.dataset.tooltip;
    
    if (!count || !tooltipHtml) return;
    
    // Position tooltip near the cell
    const rect = dayCell.getBoundingClientRect();
      const wrapperRect = tooltip.parentElement.getBoundingClientRect();
    
    tooltip.innerHTML = tooltipHtml;
    tooltip.style.display = 'block';
    
    // Calculate position (centered above the cell)
    const tooltipWidth = tooltip.offsetWidth;
    const left = rect.left - wrapperRect.left + rect.width / 2 - tooltipWidth / 2;
    const top = rect.top - wrapperRect.top - tooltip.offsetHeight - 8;
    
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  function handleDayLeave() {
    elems.tooltip.style.display = 'none';
  }

  function handleDayClick(event) {
    const dayCell = event.target;
    const dateStr = dayCell.dataset.date;
    
    if (!dateStr) return;
    
    // Set filter to show contributions from this date
    elems.filterFrom.value = dateStr;
    elems.filterTo.value = dateStr;
    applyFilters();
    
    // Scroll to table
    document.querySelector('.mc-table-card').scrollIntoView({ 
      behavior: 'smooth',
      block: 'start'
    });
  }

  function navigateYear(direction) {
    currentYear += direction;
    processContributionsData(filtered);
  }

  function resetView() {
    currentYear = new Date().getFullYear();
    processContributionsData(filtered);
  }

  function applyFilters() {
    const search = elems.filterSearch.value.toLowerCase();
    const fromDateStr = elems.filterFrom.value;
    const toDateStr = elems.filterTo.value;

    const fromDate = fromDateStr ? new Date(fromDateStr) : null;
    const toDate = toDateStr ? new Date(toDateStr) : null;

    if (fromDate && toDate && fromDate > toDate) {
      elems.state.textContent = 'Start date must be on or before end date';
      filtered = [];
      return;
    }

    elems.state.textContent = '';

    filtered = allData.filter(d => {
      if (elems.filterCampaign.value && d.campaign !== elems.filterCampaign.value) return false;
      if (elems.filterLang.value && d.lang !== elems.filterLang.value) return false;
      if (elems.filterEditType.value && d.edit_type !== elems.filterEditType.value) return false;
      if (fromDate && new Date(d.date) < fromDate) return false;
      if (toDate && new Date(d.date) > toDate) return false;
      if (search && !d.file.toLowerCase().includes(search)) return false;
      return true;
    });

    // Update contributions data with filtered results
    processContributionsData(filtered);
    
    updateSummary();
    updateCharts();
    currentPage = 1;
    renderTable();
  }

  function populateLanguageSelect(data) {
    const select = elems.filterLang;
    if (!select) return;

    const firstOption = select.querySelector('option');
    const defaultLabel = (firstOption && firstOption.textContent) || 'Any';
    const languages = [...new Set(
      data
        .map(d => (d.lang || '').trim())
        .filter(Boolean)
    )].sort((a, b) => a.localeCompare(b));

    select.innerHTML = '';
    const anyOpt = document.createElement('option');
    anyOpt.value = '';
    anyOpt.textContent = defaultLabel;
    select.appendChild(anyOpt);

    languages.forEach(lang => {
      const opt = document.createElement('option');
      opt.value = lang;
      opt.textContent = lang;
      select.appendChild(opt);
    });
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
        const fileTitle = (d.file || '').replace(/^File:/i, '');
        const fileUrl = `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(fileTitle)}`;
        const campaignUrl = d.campaign_id ? `/campaigns/${d.campaign_id}` : null;
        elems.tbody.insertAdjacentHTML(
          'beforeend',
          `<tr>
            <td>${d.date}</td>
            <td>${campaignUrl ? `<a href="${campaignUrl}" target="_blank" rel="noopener noreferrer">${d.campaign}</a>` : d.campaign}</td>
            <td><a href="${fileUrl}" target="_blank" rel="noopener noreferrer">${d.file}</a></td>
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
      el.addEventListener('input', applyFilters)
    );
    elems.filterSearch.addEventListener('input', debounce(applyFilters, 300));
    elems.resetBtn.addEventListener('click', () => {
      document.querySelectorAll('.mc-filter-input').forEach(i => i.value = '');
      applyFilters();
    });
    
    // Grid navigation events
    if (elems.prevYearBtn) {
      elems.prevYearBtn.addEventListener('click', () => navigateYear(-1));
    }
    
    if (elems.nextYearBtn) {
      elems.nextYearBtn.addEventListener('click', () => navigateYear(1));
    }
    
    if (elems.resetViewBtn) {
      elems.resetViewBtn.addEventListener('click', resetView);
    }
  }

  function debounce(fn, wait) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function mockData() {
    const data = [];
    const today = new Date();
    const startDate = new Date();
    startDate.setFullYear(startDate.getFullYear() - 1);
    
    // Generate mock data for the last year
    const daysDiff = Math.floor((today - startDate) / (1000 * 60 * 60 * 24));
    
    for (let i = 0; i <= daysDiff; i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);
      const dateStr = date.toISOString().split('T')[0];
      
      // Create activity pattern similar to GitHub
      let dailyContributions = 0;
      
      // Make weekdays more active than weekends
      const dayOfWeek = date.getDay();
      const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
      
      // Random but with patterns
      const rand = Math.random();
      if (isWeekend) {
        if (rand < 0.8) dailyContributions = 0;
        else if (rand < 0.95) dailyContributions = Math.floor(Math.random() * 3);
        else dailyContributions = Math.floor(Math.random() * 5) + 3;
      } else {
        if (rand < 0.3) dailyContributions = 0;
        else if (rand < 0.6) dailyContributions = Math.floor(Math.random() * 3);
        else if (rand < 0.8) dailyContributions = Math.floor(Math.random() * 5) + 3;
        else dailyContributions = Math.floor(Math.random() * 6) + 5;
      }
      
      for (let j = 0; j < dailyContributions; j++) {
        data.push({
          date: dateStr,
          campaign: ['Birds', 'Nature', 'Art', 'History', 'Science'][Math.floor(Math.random() * 5)],
          file: `File_${dateStr.replace(/-/g, '')}_${j}.jpg`,
          edit_type: ['caption', 'depicts', 'rotate', 'describe'][Math.floor(Math.random() * 4)],
          country: ['US', 'UK', 'DE', 'FR', 'JP'][Math.floor(Math.random() * 5)],
          lang: ['en', 'es', 'fr', 'de', 'ja'][Math.floor(Math.random() * 5)]
        });
      }
    }
    
    return data;
  }

  // Initialize
  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', () => {
        fetchCampaignOptions();
        fetchContributions();
      })
    : (fetchCampaignOptions(), fetchContributions());
})();