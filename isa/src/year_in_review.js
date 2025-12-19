(function () {
  'use strict';

  const API_BASE = '/api/user';
  const currentYear = new Date().getFullYear();
  let selectedYear = currentYear;

  const elems = {
    username: document.getElementById('yr-username'),
    currentYear: document.getElementById('yr-current-year'),
    prevYearBtn: document.getElementById('yr-prev-year'),
    nextYearBtn: document.getElementById('yr-next-year'),

    // Stat values
    depictsCount: document.getElementById('depicts-count'),
    captionsCount: document.getElementById('captions-count'),
    campaignsCount: document.getElementById('campaigns-count'),
    languagesCount: document.getElementById('languages-count'),
    captionsSubtitle: document.getElementById('captions-subtitle'),

    // Additional stats
    totalEdits: document.getElementById('total-edits'),

    // Campaigns list
    campaignsList: document.getElementById('yr-campaigns-list'),

    // Modal elements
    imageModal: document.getElementById('yr-image-modal'),
    imageCanvas: document.getElementById('yr-image-canvas'),
    closeModalBtn: document.getElementById('yr-close-modal'),
    generateImageBtn: document.getElementById('yr-generate-image'),
    downloadImageBtn: document.getElementById('yr-download-image'),
    copyImageBtn: document.getElementById('yr-copy-image'),
    shareStatsBtn: document.getElementById('yr-share-stats')
  };

  let yearStats = {};

  function isDevUser() {
    return elems.username && elems.username.textContent.trim() === 'Dev';
  }

  function init() {
    fetchYearStats();
    attachEventListeners();
    updateYearDisplay();
  }

  function fetchYearStats() {
    // Show loading state
    showLoading(true);

    // Fetch year statistics
    fetch(`${API_BASE}/year-stats?year=${selectedYear}`)
      .then(response => {
        console.log('Response status:', response.status);
        if (!response.ok) throw new Error('Failed to fetch year stats');
        return response.json();
      })
      .then(data => {
        if (data.success) {
          updateStatsDisplay(data.stats);
          updateAdditionalStats(data.stats);
          updateCampaignsList(data.top_campaigns || []);
        } else {
          throw new Error(data.error || 'Unknown error');
        }
      })
      .catch(error => {
        console.error('Error fetching year stats:', error);
        if (isDevUser()) {
          // For Dev user, fall back to mock data to keep the page useful
          const mockStats = generateMockStats();
          updateStatsDisplay(mockStats);
          updateAdditionalStats(mockStats);
          fetchTopCampaigns(true);
        } else {
          // For all other users, do NOT use mock/random data
          const emptyStats = {
            total_edits: 0,
            depicts_edits: 0,
            caption_edits: 0,
            campaigns_count: 0,
            languages_count: 0
          };
          updateStatsDisplay(emptyStats);
          updateAdditionalStats(emptyStats);
          // Still try to load campaigns from the DB
          fetchTopCampaigns(false);
        }
      })
      .finally(() => {
        showLoading(false);
      });
  }

  function fetchTopCampaigns(allowMockForDev = false) {
    // Fetch top campaigns separately
    fetch(`${API_BASE}/top-campaigns?limit=6`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          updateCampaignsList(data.campaigns);
        } else {
          // When backend reports failure, do not invent data for non-Dev users
          if (allowMockForDev && isDevUser()) {
            updateCampaignsList(generateMockCampaigns());
          } else {
            updateCampaignsList([]);
          }
        }
      })
      .catch(error => {
        console.error('Error fetching campaigns:', error);
        if (allowMockForDev && isDevUser()) {
          updateCampaignsList(generateMockCampaigns());
        } else {
          updateCampaignsList([]);
        }
      });
  }

  function updateStatsDisplay(stats) {
    // Update main stats
    elems.depictsCount.textContent = (stats.depicts_edits !== undefined && stats.depicts_edits !== null ? stats.depicts_edits.toLocaleString() : '0');
    elems.captionsCount.textContent = (stats.caption_edits !== undefined && stats.caption_edits !== null ? stats.caption_edits.toLocaleString() : '0');
    elems.campaignsCount.textContent = (stats.campaigns_count !== undefined && stats.campaigns_count !== null ? stats.campaigns_count.toLocaleString() : '0');
    elems.languagesCount.textContent = (stats.languages_count !== undefined && stats.languages_count !== null ? stats.languages_count.toLocaleString() : '0');


    // Update captions subtitle with character count estimate
    const avgCharsPerCaption = 50; // Average characters per caption
    const totalChars = (stats.caption_edits || 0) * avgCharsPerCaption;
    elems.captionsSubtitle.textContent = formatCharacterCount(totalChars);

    // Store stats for image generation
    yearStats = stats;
  }

  function formatCharacterCount(chars) {
    if (chars >= 1000000) {
      return `${(chars / 1000000).toFixed(1)}M+ characters of text!`;
    } else if (chars >= 1000) {
      return `${(chars / 1000).toFixed(1)}K+ characters of text!`;
    }
    return `${chars.toLocaleString()} characters of text!`;
  }

  function updateAdditionalStats(stats) {
    // This section is optional in the template; guard against missing node
    if (!elems.totalEdits) return;
    elems.totalEdits.textContent = (stats.total_edits !== undefined && stats.total_edits !== null) ? stats.total_edits.toLocaleString() : '0';

  }


  function updateCampaignsList(campaigns) {
    // Campaigns list section is optional; no-op if container is absent
    if (!elems.campaignsList) return;

    elems.campaignsList.innerHTML = '';

    campaigns.forEach(campaign => {
      const campaignItem = document.createElement('div');
      campaignItem.className = 'yr-campaign-item';

      const campaignName = extractCampaignName(campaign.html || campaign.name);
      const editCount = campaign.edits || 0;

      campaignItem.innerHTML = `
        <div class="yr-campaign-name">${campaignName}</div>
        <div class="yr-campaign-stats">
          <span class="yr-campaign-edits">${editCount.toLocaleString()} edits</span>
          <span class="yr-campaign-date">${selectedYear}</span>
        </div>
      `;

      elems.campaignsList.appendChild(campaignItem);
    });
  }

  function extractCampaignName(html) {
    if (!html) return 'Unknown Campaign';
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const strong = tmp.querySelector('strong');
    return (strong ? strong.textContent : tmp.textContent).trim() || 'Unknown Campaign';
  }

  function updateYearDisplay() {
    elems.currentYear.textContent = selectedYear;
  }

  function showLoading(isLoading) {
    // You can implement a loading spinner here
    if (isLoading) {
      document.body.style.opacity = '0.8';
      document.body.style.pointerEvents = 'none';
    } else {
      document.body.style.opacity = '1';
      document.body.style.pointerEvents = 'auto';
    }
  }

  // Image generation helpers
  function parseStatNumber(valueFromStats, fallbackText) {
    if (typeof valueFromStats === 'number' && !Number.isNaN(valueFromStats)) {
      return valueFromStats;
    }
    if (!fallbackText) return 0;
    const cleaned = String(fallbackText).replace(/[^0-9]/g, '');
    const parsed = parseInt(cleaned, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  function drawRoundedRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + width - r, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + r);
    ctx.lineTo(x + width, y + height - r);
    ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
    ctx.lineTo(x + r, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function drawStatCard(ctx, config) {
    const { x, y, width, height, color, label, value, subtitle } = config;

    // Card background with subtle shadow (matches .yr-stat-card)
    ctx.save();
    ctx.shadowColor = 'rgba(15, 23, 42, 0.10)';
    ctx.shadowBlur = 20;
    ctx.shadowOffsetY = 10;
    ctx.fillStyle = '#ffffff';
    drawRoundedRect(ctx, x, y, width, height, 16);
    ctx.fill();
    ctx.restore();

    // Icon block (matches .yr-card-icon)
    const iconSize = 40;
    const iconX = x + 20;
    const iconY = y + 20;
    ctx.save();
    ctx.fillStyle = color;
    drawRoundedRect(ctx, iconX, iconY, iconSize, iconSize, 10);
    ctx.fill();
    ctx.restore();

    // Label next to icon (matches .yr-card-label)
    ctx.save();
    ctx.textAlign = 'left';
    ctx.fillStyle = '#64748b';
    ctx.font = '700 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.fillText(label.toUpperCase(), iconX + iconSize + 12, iconY + 26);

    // Main value (matches .yr-stat-value)
    ctx.fillStyle = '#1e293b';
    ctx.font = '800 48px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.fillText(value.toLocaleString(), x + 20, y + 110);

    // Subtitle (matches .yr-stat-subtitle)
    if (subtitle) {
      ctx.fillStyle = '#64748b';
      ctx.font = '500 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      ctx.fillText(subtitle, x + 20, y + 140);
    }
    ctx.restore();
  }

  // Image generation and modal functions
  // Image generation and modal functions
  // Returns a Promise that resolves when the canvas has content
  function generateImage() {
    const container = document.querySelector('.year-review-container');

    // Fallback if html2canvas is not available
    if (!container || typeof window.html2canvas !== 'function') {
      console.error('html2canvas is not available; cannot capture Year in Review.');
      alert('Unable to generate image preview. Please try again later.');
      return Promise.reject(new Error('html2canvas not available'));
    }

    showLoading(true);

    return new Promise((resolve, reject) => {
      // First ensure the logo image is fully loaded
      const logoImg = container.querySelector('.yr-domain-logo img');

      const proceed = () => captureContainer(container, resolve, reject);

      if (logoImg && !logoImg.complete) {
        logoImg.addEventListener('load', proceed, { once: true });
        logoImg.addEventListener('error', proceed, { once: true });
      } else {
        proceed();
      }
    });

    function captureContainer(containerElement, resolve, reject) {
      window.html2canvas(containerElement, {
        backgroundColor: null,
        scale: 2,
        logging: false,
        useCORS: true,
        allowTaint: true,
        imageTimeout: 0, // Disable timeout for images
        onclone: function (clonedDoc) {
          // Tweak cloned layout so the captured image has tighter,
          // content-based height instead of full viewport height.
          const clonedContainer = clonedDoc.querySelector('.year-review-container');
          if (clonedContainer) {
            clonedContainer.style.minHeight = 'auto';
            clonedContainer.style.margin = '0 auto';
            clonedContainer.style.paddingTop = '2rem';
            clonedContainer.style.paddingBottom = '2rem';
          }

          // Ensure logo has proper dimensions in cloned document
          const clonedLogo = clonedDoc.querySelector('.yr-domain-logo img');
          if (clonedLogo) {
            clonedLogo.style.width = '100%';
            clonedLogo.style.height = '100%';
            clonedLogo.style.objectFit = 'contain';
          }
        }
      })
        .then(capturedCanvas => {
          const targetCanvas = elems.imageCanvas;
          const ctx = targetCanvas.getContext('2d');

          // Clear and resize target canvas
          targetCanvas.width = capturedCanvas.width;
          targetCanvas.height = capturedCanvas.height;

          // Fill with background color matching the container
          ctx.fillStyle = '#f8fafc';
          ctx.fillRect(0, 0, targetCanvas.width, targetCanvas.height);

          // Draw the captured content
          ctx.drawImage(capturedCanvas, 0, 0);

          elems.imageModal.style.display = 'flex';
          resolve();
        })
        .catch(error => {
          console.error('Failed to capture Year in Review container:', error);
          alert('Failed to generate image. Please try again.');
          reject(error);
        })
        .finally(() => {
          showLoading(false);
        });
    }
  }

  function downloadImage() {
    const canvas = elems.imageCanvas;
    const link = document.createElement('a');
    link.download = `year-in-review-${selectedYear}-${elems.username.textContent}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  }

  async function copyImageToClipboard() {
    try {
      const canvas = elems.imageCanvas;
      const blob = await new Promise(resolve => canvas.toBlob(resolve));
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);
      alert('Image copied to clipboard!');
    } catch (error) {
      console.error('Failed to copy image:', error);
      alert('Failed to copy image to clipboard. Please try downloading instead.');
    }
  }

  async function shareStats() {
    const username = (elems.username && elems.username.textContent) ? elems.username.textContent : 'user';

    try {
      // Always (re)generate the image to ensure canvas has up-to-date content
      await generateImage();

      const canvas = elems.imageCanvas;

      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob(result => {
          if (result) {
            resolve(result);
          } else {
            reject(new Error('Failed to create image blob'));
          }
        }, 'image/png');
      });

      const fileName = `year-in-review-${selectedYear}-${username}.png`;
      const filesArray = [new File([blob], fileName, { type: 'image/png' })];

      // Prefer Web Share API with file support when available
      if (navigator.canShare && navigator.canShare({ files: filesArray })) {
        await navigator.share({
          title: `My ${selectedYear} Year in Review - ${username}`,
          text: `Check out my Wikimedia Commons contributions for ${selectedYear}!`,
          files: filesArray
        });
        return;
      }

      // Fallback to regular share (link only)
      if (navigator.share) {
        await navigator.share({
          title: `My ${selectedYear} Year in Review - ${username}`,
          text: `Check out my Wikimedia Commons contributions for ${selectedYear}!`,
          url: window.location.href
        });
        return;
      }

      // Final fallback: copy link to clipboard
      await navigator.clipboard.writeText(window.location.href);
      alert('Link copied to clipboard! Share it with your friends!');
    } catch (error) {
      console.error('Error sharing stats:', error);
      alert('Unable to share the image automatically. Please try downloading the image and sharing it manually.');
    }
  }

  function attachEventListeners() {
    // Year navigation
    elems.prevYearBtn.addEventListener('click', () => {
      selectedYear--;
      updateYearDisplay();
      fetchYearStats();
    });

    elems.nextYearBtn.addEventListener('click', () => {
      if (selectedYear < currentYear) {
        selectedYear++;
        updateYearDisplay();
        fetchYearStats();
      }
    });

    // Card navigation buttons
    document.querySelectorAll('.yr-card-prev').forEach(btn => {
      btn.addEventListener('click', (e) => {
        selectedYear--;
        updateYearDisplay();
        fetchYearStats();
      });
    });

    document.querySelectorAll('.yr-card-next').forEach(btn => {
      btn.addEventListener('click', (e) => {
        if (selectedYear < currentYear) {
          selectedYear++;
          updateYearDisplay();
          fetchYearStats();
        }
      });
    });

    // Image generation and sharing
    elems.generateImageBtn.addEventListener('click', generateImage);
    elems.downloadImageBtn.addEventListener('click', downloadImage);
    elems.copyImageBtn.addEventListener('click', copyImageToClipboard);
    elems.shareStatsBtn.addEventListener('click', shareStats);
    elems.closeModalBtn.addEventListener('click', () => {
      elems.imageModal.style.display = 'none';
    });

    // Close modal when clicking outside
    elems.imageModal.addEventListener('click', (e) => {
      if (e.target === elems.imageModal) {
        elems.imageModal.style.display = 'none';
      }
    });
  }

  // Mock data generators for development
  function generateMockStats() {
    return {
      total_edits: Math.floor(Math.random() * 200) + 50,
      depicts_edits: Math.floor(Math.random() * 80) + 10,
      caption_edits: Math.floor(Math.random() * 60) + 10,
      campaigns_count: Math.floor(Math.random() * 8) + 1,
      languages_count: Math.floor(Math.random() * 5) + 1
    };
  }

  function generateMockCampaigns() {
    const campaignNames = [
      'Birds of the World',
      'Cultural Heritage',
      'Science Images',
      'Historical Documents',
      'Art Collection',
      'Nature Photography'
    ];

    return campaignNames.map(name => ({
      name: name,
      edits: Math.floor(Math.random() * 50) + 5,
      html: `<strong>${name}</strong>`
    }));
  }

  // Initialize when DOM is ready
  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
})();