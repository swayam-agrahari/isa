/*********** Participate page ***********/

import {ParticipationManager} from './participation-manager.js';
import {getUrlParameters, shuffle, flashMessage} from './utils.js';
import {generateGuid} from './guid-generator.js';

// Get i18n strings safely
var i18nStrings = {};
try {
    i18nStrings = JSON.parse($('.hidden-i18n-text').text().trim());
} catch (e) {
    console.error('Failed to parse i18n strings:', e);
    // Use default English strings as fallback
    i18nStrings = {
        "No images found for this campaign!": "No images found for this campaign!",
        "Something went wrong getting campaign images": "Something went wrong getting campaign images",
        "Search for things you see in the image": "Search for things you see in the image",
        "minimise metadata from Commons": "minimise metadata from Commons",
        "show all metadata from Commons": "show all metadata from Commons",
        "Success! Depicted items saved to Wikimedia Commons": "Success! Depicted items saved to Wikimedia Commons",
        "Success! Captions saved to Wikimedia Commons": "Success! Captions saved to Wikimedia Commons",
        "Oops! Something went wrong, your edits have not been saved to Wikimedia Commons": "Oops! Something went wrong, your edits have not been saved to Wikimedia Commons",
        "Are you sure you want to navigate to another image? You have unsaved changes which will be lost.": "Are you sure you want to navigate to another image? You have unsaved changes which will be lost.",
        "Click 'OK' to proceed anyway, or 'Cancel' if you want to save changes first.": "Click 'OK' to proceed anyway, or 'Cancel' if you want to save changes first.",
        "Remove this depicted item": "Remove this depicted item",
        "Mark this depicted item as prominent": "Mark this depicted item as prominent",
        "Mark this depicted item as NOT prominent": "Mark this depicted item as NOT prominent"
    };
}

var campaignId = getCampaignId(),
    wikiLovesCountry = getWikiLovesCountry(),
    isWikiLovesCampaign = !!wikiLovesCountry,
    isUserLoggedIn = false,
    csrf_token = "{{ csrf_token() }}",
    editSession,
    enhancedUI;

// Pagination state
let currentPage = 1;
const perPage = 10;
let allLoadedImages = [];
let hasMoreImages = true;

// Helper to load images from backend
function loadImages(page) {
    let imagesUrl = `../../campaigns/${campaignId}/images?page=${page}&per_page=${perPage}`;
    if (isWikiLovesCampaign && wikiLovesCountry) {
        imagesUrl += `/${encodeURIComponent(wikiLovesCountry)}`;
    }
    return $.get(imagesUrl).then(data => {
        // Support both old and new backend formats
        if (Array.isArray(data)) {
            if (data.length < perPage) hasMoreImages = false;
            allLoadedImages = allLoadedImages.concat(data);
        } else {
            if (data.images) {
                allLoadedImages = allLoadedImages.concat(data.images);
                hasMoreImages = data.has_more;
            }
        }
    });
}

function initParticipation() {
    // Initial load
    loadImages(currentPage).then(() => {
        if (allLoadedImages.length === 0) {
            hideLoadingOverlay();
            alert(i18nStrings["No images found for this campaign!"]);
            window.location.href = '../' + campaignId;
            return;
        }
        
        shuffle(allLoadedImages);
        editSession = new ParticipationManager(allLoadedImages, campaignId, wikiLovesCountry, isUserLoggedIn);

        // Initialize enhanced UI if available
        if (typeof window.enhancedParticipate !== 'undefined') {
            enhancedUI = window.enhancedParticipate;
            enhancedUI.initEnhancedFeatures();
        }

        if (getUrlParameters().image) {
            var image = Number.parseInt(getUrlParameters().image);
            var imageIndex = allLoadedImages.indexOf(image);
            if (imageIndex !== -1) {
                editSession.setImageIndex(imageIndex);
            }
        } else {
            editSession.imageChanged();
        }

        hideLoadingOverlay();
    }).catch(function(err) {
        console.log("error loading campaign images", err);
        hideLoadingOverlay();
        alert(i18nStrings["Something went wrong getting campaign images"]);
        window.location.href = '../' + campaignId;
    });
}

///////// Campaign images /////////

// Check if user is logged in
$.getJSON('../../api/login-test')
    .then(function(response) {
        isUserLoggedIn = response.is_logged_in;
        initParticipation();
    })
    .fail(function(err) {
        console.log("error checking login status", err);
        isUserLoggedIn = false;
        initParticipation();
    });

///////// Depicts search box /////////

function searchResultsFormat(state) {
    if (!state.id) {
      return state.text;
    }
    var $label = $("<span>")
        .addClass("search-result-label")
        .text(state.text);
    var $description = $("<span>")
        .addClass("search-result-description")
        .text(state.description);
    var $state = $("<div>").append(
        $label,
        $("<br>"),
        $description
    );
    return $state;
  }

(function setUpDepictsSearch(){
    $( '#depicts-select' ).select2( {
        placeholder: i18nStrings['Search for things you see in the image'],
        delay: 250,
        minimumResultsForSearch: 1,
        maximumSelectionLength: 4,
        ajax: {
            type: 'GET',
            dataType: 'json',
            url: function(t) {
                return '../../api/search-depicts/' + campaignId;
            }
        },
        templateResult: searchResultsFormat,
    });

    $('#depicts-select').on('select2:select', function(ev) {
        // Add new depict statement to the UI when user selects result
        var selected = ev.params.data;

        // Generate a new unique statement ID
        var statementId = generateStatementId(editSession.imageMediaId);

        editSession.addDepictStatement (
            selected.id,
            selected.text,
            selected.description,
            false /* isProminent */,
            statementId
        );
        $(this).val(null).trigger('change');
    })
  })();

///////// Event handlers /////////

$('#expand-meta-data').click(function() {
    $('.image-desc').toggleClass('expand');

    if ($('.image-desc').hasClass('expand')) {
        // expanded
        var minimiseText = i18nStrings['minimise metadata from Commons'];
        $('#expand-meta-data').html('<i class="fas fa-caret-up"></i>&nbsp; ' + minimiseText);
    } else {
        // collpased
        var maximiseText = i18nStrings['show all metadata from Commons'];
        $('#expand-meta-data').html('<i class="fas fa-caret-down"></i>&nbsp; ' + maximiseText);
    }
})

$('.next-image-btn').click(function () {
    if (editSession.imageIndex >= allLoadedImages.length - 1 && hasMoreImages) {
        currentPage++;
        loadImages(currentPage).then(() => {
            editSession.updateImages(allLoadedImages);
            editSession.nextImage();
        });
    } else {
        editSession.nextImage();
    }
});

$('.previous-image-btn').click(function(ev) {
    editSession.previousImage();
})

$('.caption-input').on('input', function() {
    editSession.captionDataChanged();
})

// Click to remove depicts tags
$('.depict-tag-group').on('click','.depict-tag-btn', function(ev) {
    $(this).parents('.depict-tag-item').remove();
    editSession.depictDataChanged();
})

// Click to change isProminent for depicts tags
$('.depict-tag-group').on('click','.prominent-btn', function(ev) {
    $(this).toggleClass('active');
    editSession.depictDataChanged();
})

$('.edit-publish-btn-group').on('click', 'button', function() {
    var editType = $(this).parent().attr('edit-type');

    if ( $(this).hasClass('cancel-edits-btn') ) {
        if (editType === "depicts") {
            editSession.resetDepictStatements();
        }
        if (editType === "captions") {
            editSession.resetCaptions();
        }
    }

    if ( $(this).hasClass('publish-edits-btn') ) {
        editSession.postContribution(editType)
    }

})

function getCampaignId () {
    var parts = window.location.pathname.split("/");
    return parseInt(parts[parts.length - 2]);
}

function getWikiLovesCountry () {
    var country = getUrlParameters().country;
    return (country) ? decodeURIComponent(country) : '';
}

function generateStatementId(mediaId) {
    return mediaId + '$' + generateGuid();
}

function hideLoadingOverlay() {
    $('.loading-overlay').fadeOut('slow', function() {
        $(this).remove();
    });
}

// Override the imageChanged method to integrate with enhanced UI
const originalImageChanged = ParticipationManager.prototype.imageChanged;
ParticipationManager.prototype.imageChanged = function() {
    originalImageChanged.apply(this, arguments);
    
    // Notify enhanced UI
    if (enhancedUI) {
        $(document).trigger('imageChanged', {
            imageFileName: this.imageFileName,
            imageIndex: this.imageIndex,
            totalImages: this.images.length
        });
        enhancedUI.updateProgress(this.imageIndex + 1, this.getCompletedCount(), this.images.length);
    }
};

// Add getCompletedCount method if it doesn't exist
if (!ParticipationManager.prototype.getCompletedCount) {
    ParticipationManager.prototype.getCompletedCount = function() {
        // Implement your logic to count completed images
        return 0; // Placeholder
    };
}