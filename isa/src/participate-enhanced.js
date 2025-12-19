// Enhanced participate.js with improved UX - Fixed version (without AI suggestions)
$(document).ready(function() {
    // Initialize enhanced features after DOM is ready
    setTimeout(initEnhancedFeatures, 100);
});

function initEnhancedFeatures() {
    try {
        // Initialize tooltips if Bootstrap is available
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
        
        // Initialize popovers if Bootstrap is available
        if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
            var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
            popoverTriggerList.map(function (popoverTriggerEl) {
                return new bootstrap.Popover(popoverTriggerEl, {
                    trigger: 'focus',
                    html: true
                });
            });
        }
        
        // Initialize image zoom
        initImageZoom();
        
        // Initialize character counters for captions
        initCharacterCounters();
        
        // Initialize keyboard shortcuts
        initKeyboardShortcuts();
        
        // Initialize progress tracking
        initProgressTracking();
        
        // Initialize event listeners
        initEventListeners();
        
        console.log('Enhanced features initialized');
    } catch (e) {
        console.error('Error initializing enhanced features:', e);
    }
}

function initImageZoom() {
    let isZoomed = false;
    let zoomLevel = 1;
    
    $(document).on('click', '.img-holder img', function() {
        if (!isZoomed) {
            zoomLevel = 1.5;
            $(this).css({
                'transform': `scale(${zoomLevel})`,
                'cursor': 'zoom-out'
            });
            $(this).closest('.img-holder').addClass('zoomed');
            isZoomed = true;
        } else {
            zoomLevel = 1;
            $(this).css({
                'transform': 'scale(1)',
                'cursor': 'zoom-in'
            });
            $(this).closest('.img-holder').removeClass('zoomed');
            isZoomed = false;
        }
    });
    
    $('.zoom-in').on('click', function() {
        zoomLevel = Math.min(zoomLevel + 0.25, 3);
        $('.img-holder img').css('transform', `scale(${zoomLevel})`);
        $('.img-holder').addClass('zoomed');
        isZoomed = true;
    });
    
    $('.zoom-out').on('click', function() {
        zoomLevel = Math.max(zoomLevel - 0.25, 1);
        $('.img-holder img').css('transform', `scale(${zoomLevel})`);
        if (zoomLevel === 1) {
            $('.img-holder').removeClass('zoomed');
            isZoomed = false;
        }
    });
}

function initCharacterCounters() {
    $('.caption-input').on('input', function() {
        const charCount = $(this).val().length;
        const maxLength = $(this).attr('maxlength') || 255;
        const lang = $(this).attr('lang');
        const counter = $(`.char-counter[data-lang="${lang}"]`);
        
        if (counter.length) {
            counter.text(`${charCount}/${maxLength}`);
            
            // Color code based on length
            if (charCount > 200) {
                counter.addClass('text-warning').removeClass('text-muted text-success');
            } else if (charCount > 50) {
                counter.addClass('text-success').removeClass('text-muted text-warning');
            } else {
                counter.addClass('text-muted').removeClass('text-success text-warning');
            }
        }
    });
    
    // Initialize counters
    $('.caption-input').each(function() {
        $(this).trigger('input');
    });
}

function initKeyboardShortcuts() {
    $(document).on('keydown', function(e) {
        // Don't trigger shortcuts when user is typing in inputs
        if ($(e.target).is('input, textarea, select')) return;
        
        switch(e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                $('.previous-image-btn').trigger('click');
                break;
            case 'ArrowRight':
                e.preventDefault();
                $('.next-image-btn').trigger('click');
                break;
            case 'Escape':
                // Cancel current edits
                if (e.shiftKey) {
                    $('.cancel-edits-btn:not(:disabled)').trigger('click');
                }
                break;
            case 's':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    $('.publish-edits-btn:not(:disabled)').first().trigger('click');
                }
                break;
        }
    });
}

function initProgressTracking() {
    // This will be updated by the main participation manager
    updateProgress(0, 0, 0);
}

function updateProgress(current, completed, total) {
    try {
        // Update stats
        if ($('#current-image-number').length) {
            $('#current-image-number').text(current);
        }
        if ($('#completed-count').length) {
            $('#completed-count').text(completed);
        }
        if ($('#remaining-count').length) {
            $('#remaining-count').text(total - completed);
        }
        if ($('#bottom-image-number').length) {
            $('#bottom-image-number').text(current);
        }
        if ($('#bottom-total-images').length) {
            $('#bottom-total-images').text(total);
        }
        if ($('#bottom-completed').length) {
            $('#bottom-completed').text(completed);
        }
        if ($('#mobile-image-number').length) {
            $('#mobile-image-number').text(current);
        }
        if ($('#mobile-total-images').length) {
            $('#mobile-total-images').text(total);
        }
        
        // Update progress bar
        const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
        const $progressBar = $('#session-progress');
        if ($progressBar.length) {
            $progressBar.css('width', `${percentage}%`);
        }
        if ($('#progress-text').length) {
            $('#progress-text').text(`${completed}/${total}`);
        }
        
        // Update progress bar color based on progress
        if ($progressBar.length) {
            $progressBar.removeClass('bg-success bg-warning bg-danger');
            
            if (percentage >= 75) {
                $progressBar.addClass('bg-success');
            } else if (percentage >= 25) {
                $progressBar.addClass('bg-warning');
            } else {
                $progressBar.addClass('bg-danger');
            }
        }
    } catch (e) {
        console.error('Error updating progress:', e);
    }
}

function initEventListeners() {
    // Toggle metadata panel
    $('.toggle-metadata').on('click', function(e) {
        e.preventDefault();
        const $metadata = $('#imageMetadata');
        $metadata.collapse('toggle');
        
        const $icon = $(this).find('i');
        if ($metadata.hasClass('show')) {
            $icon.removeClass('fa-info-circle').addClass('fa-times');
            $(this).attr('title', i18n['minimise metadata from Commons']);
        } else {
            $icon.removeClass('fa-times').addClass('fa-info-circle');
            $(this).attr('title', i18n['show all metadata from Commons']);
        }
    });
    
    // Update Commons link
    $(document).on('imageChanged', function(e, data) {
        if (data && data.imageFileName) {
            const commonsUrl = `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(data.imageFileName)}`;
            $('#open-commons-link').attr('href', commonsUrl);
        }
    });
}

// Enhanced flash message function
function showFlashMessage(type, message, duration = 3000) {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const $alert = $(`.isa-flash-message.${alertClass}`);
    
    if ($alert.length) {
        $alert.find('.message-content').text(message);
        $alert.removeClass('fade').addClass('show');
        
        // Auto-dismiss after duration
        setTimeout(() => {
            $alert.removeClass('show').addClass('fade');
        }, duration);
    }
}

// Enhanced category display
function updateCategories(categories) {
    const $container = $('#image_categories');
    if (!$container.length) return;
    
    $container.empty();
    
    if (!categories || categories.length === 0) {
        $container.html('<span class="text-muted">No categories</span>');
        return;
    }
    
    // Handle both string and array formats
    if (typeof categories === 'string') {
        categories = categories.split(',').map(cat => cat.trim());
    }
    
    categories.slice(0, 5).forEach(category => {
        const $badge = $(`<span class="badge me-1 mb-1">${category}</span>`);
        $container.append($badge);
    });
    
    if (categories.length > 5) {
        const remaining = categories.length - 5;
        const $moreBadge = $(`<span class="badge bg-secondary me-1 mb-1">+${remaining} more</span>`);
        $moreBadge.attr('title', categories.slice(5).join(', '));
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            new bootstrap.Tooltip($moreBadge[0]);
        }
        $container.append($moreBadge);
    }
}

// Initialize i18n safely
let i18n = {};
try {
    i18n = JSON.parse($('.hidden-i18n-text').text().trim());
} catch (e) {
    console.error('Failed to parse i18n strings:', e);
    // Use safe defaults
    i18n = {
        'minimise metadata from Commons': 'minimise metadata from Commons',
        'show all metadata from Commons': 'show all metadata from Commons',
        'No categories': 'No categories'
    };
}

// Export functions for main participate.js to use
window.enhancedParticipate = {
    updateProgress,
    showFlashMessage,
    updateCategories,
    initEnhancedFeatures
};

// Add CSS for enhanced features (removed AI suggestions related styles)
const enhancedStyles = `
.zoomed {
    overflow: auto;
}

.zoomed img {
    transform-origin: center center;
}

.char-counter {
    font-size: 0.75rem;
}

.char-counter.text-warning {
    color: #ffc107 !important;
}

.char-counter.text-success {
    color: #198754 !important;
}

.loading-overlay {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

@media (max-width: 768px) {
    .mobile-bottom-nav {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 1030;
    }
    
    .main-content {
        padding-bottom: 70px;
    }
}
`;

// Add styles to document
const styleSheet = document.createElement('style');
styleSheet.textContent = enhancedStyles;
document.head.appendChild(styleSheet);