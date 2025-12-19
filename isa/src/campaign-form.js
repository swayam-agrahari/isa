var i18nStrings = JSON.parse($('.hidden-i18n-text').text());
var isWikiLovesCampaign = $('#campaign_type')[0].checked;
var categoriesAreValid = false;
var WIKI_URL = 'https://commons.wikimedia.org/'; // Or your specific wiki

$('#start_date_datepicker').attr({ 'data-toggle': 'datetimepicker', 'data-target': '#start_date_datepicker' });
$('#start_date_datepicker').datetimepicker({
    format: 'YYYY-MM-DD',
    useCurrent: false,
});

$('#end_date_datepicker').attr({ 'data-toggle': 'datetimepicker', 'data-target': '#end_date_datepicker' });
$('#end_date_datepicker').datetimepicker({
    format: 'YYYY-MM-DD',
    useCurrent: false
});

//Error handling helpers
function showFormErrors(messages) {
    var $errorBox = $('#campaign-form-errors');
    $errorBox.html('<ul class="mb-0">' +
        messages.map(msg => `<li>${msg}</li>`).join('')
        + '</ul>');
    $errorBox.removeClass('d-none');

    // Scroll to error box
    $('html, body').animate({
        scrollTop: $errorBox.offset().top - 100
    }, 500);
}

function clearFormErrors() {
    $('#campaign-form-errors').addClass('d-none').empty();
}

function isValidDateRange() {
    var start = $('#start_date_datepicker').datetimepicker('date');
    var end = $('#end_date_datepicker').datetimepicker('date');

    if (!start || !end) return true; // required validation handled elsewhere
    return start.isSameOrBefore(end, 'day');
}

// Populate existing categories in the UI if data present in hidden field (on update route)
var initialCategoryData = $('#categories-data').val();
if (initialCategoryData) {
    var categories = JSON.parse(initialCategoryData);
    for (var i = 0; i < categories.length; i++) {
        addSelectedCategory(categories[i].name, categories[i].depth);
    }
}

// Setup category search box
function categorySearchResultsFormat(state) {
    if (!state.id) {
        return state.text;
    }
    var $state = $('<span class="search-result-label">' + state.text + '</span>');
    return $state;
}
$(document).ready(function () {
    $('#category-search').select2({

        minimumInputLength: 1,
        placeholder: 'Search for categories...',
        ajax: {
            url: 'https://commons.wikimedia.org/w/api.php',
            dataType: 'jsonp', // Required for cross-site requests
            delay: 250,
            data: function (params) {
                return {
                    action: 'opensearch',
                    format: 'json',
                    namespace: 14, // Category namespace
                    search: params.term
                };
            },
            processResults: function (data) {
                console.log('Initializing select2 for category search');
                // data[1] is the array of results from opensearch
                return {
                    results: data[1].map(function (item) {
                        return {
                            id: item,
                            text: item
                        };
                    })
                };
            }
        },
        templateResult: categorySearchResultsFormat
    });

    $('#category-search').on('select2:select', function (ev) {
        var category = $(this).val();
        addSelectedCategory(category);
        $(this).val(null).trigger('change'); // clear the search selection
        $(this).select2("close"); // close the dropdown
        $("#update_images").prop("checked", true);
    });

    $(".category-depth-input").change(function () {
        $("#update_images").prop("checked", true);
    });
});
// Main function to add the UI elements for a new category row
// Used when category is added via search, or populating from existing campaign categories
function addSelectedCategory(name, depth) {
    var depth = depth || 0;
    var shortName = name.replace("Category:", "");
    $('#selected-categories-content').append(getCategoryRowHtml(shortName, depth));
    // show the table header if it's not visible already
    $('#selected-categories-header').show();
    if (isWikiLovesCampaign) validateWikiLovesCategories();
}

// Click event for removing categories
$('#selected-categories-content').on("click", "button.close", function (event) {
    // remove the .selected-category parent container the button is within
    $(this).closest(".selected-category").remove();

    if (isWikiLovesCampaign) validateWikiLovesCategories();

    // after removing the element, we must hide the table header if there are no rows left
    if ($('.selected-category').length < 1) {
        $('#selected-categories-header').hide();
    }
    $("#update_images").prop("checked", true);
});

// Returns the html for an individual category row, including depth option and remove button
function getCategoryRowHtml(name, depth) {
    var depth = depth || 0;
    var nameHtml = '<td class="category-name">' + name + '</td>';
    var depthHtml = '<td> <input type="number" min="0" max="5" class="category-depth-input" value=' + depth + '> </td>';
    var buttonHtml = '<td> <button type="button" class="close" aria-label="Close"> <span aria-hidden="true"> × </span> </button> </td>';
    return '<tr class="selected-category">' + nameHtml + depthHtml + buttonHtml + '</tr>';
}

// Returns category data that can be submitted to the server
function getCategoryData() {
    var categoryData = [];
    $('.selected-category').each(function (index, element) {
        var name = $(element).find('.category-name').text();
        var depth = $(element).find('.category-depth-input').val();
        categoryData.push({
            name: name,
            depth: depth
        });
    });
    return categoryData;
}

// Check if each category in the UI has the correct syntax for Wiki Loves campaign
// Add class to show valid/ivalid with green/red border
function validateWikiLovesCategories() {
    var hasValidationErrors = false;
    var isValid;
    $('.selected-category').each(function () {
        isValid = validateWikiLovesCategory(this);
        if (!isValid) hasValidationErrors = true;
    });

    if (hasValidationErrors) {
        $('.invalid-wiki-loves-warning').show();
    } else {
        $('.invalid-wiki-loves-warning').hide();
    }
    categoriesAreValid = !hasValidationErrors;
}

function validateWikiLovesCategory(element) {
    var categoryName = $(element).find('.category-name').text();
    var isValid = isValidWikiLovesSyntax(categoryName);
    if (isValid) {
        $(element).removeClass('invalid-category').addClass('valid-category');
    } else {
        $(element).removeClass('valid-category').addClass('invalid-category');
    }
    return isValid;
}

function isValidWikiLovesSyntax(categoryName) {
    var syntaxReg = /Images from Wiki Loves .+? \d{4}(?: in .+)?$/u;;
    return syntaxReg.test(categoryName);
}

function clearWikiLovesValidation() {
    $('.selected-category').each(function () {
        $(this).removeClass('invalid-category').removeClass('valid-category');
        $('.invalid-wiki-loves-warning').hide();
    });
}

//////////// Form submission ////////////

// Using click instead of submit event, as this triggers form validation
// Submit event is fired manually once categories have been checked
// Once categories confirmed checked or unchanged, refire the submit click
// but this time continue with default submit bahaviour
// Also continue with default submit if form is invalid to trigger browser warnings
// Todo: Setup custom validation for all fields as separate function
var categoriesChecked = false,
    formIsValid = false;
$('#submit').click(function (ev) {
    clearFormErrors();

    var errors = [];
    var form = $('form')[0];

    // Native required-field validation
    if (!form.checkValidity()) {
        return;
    }

    // Categories
    var categorySelections = getCategoryData();
    if (categorySelections.length === 0) {
        errors.push(i18nStrings['You must select at least one category for your campaign.']);
    }

    // Wiki Loves syntax
    if (isWikiLovesCampaign && !categoriesAreValid) {
        errors.push(
            i18nStrings['Some of the categories you have chosen do not have the correct syntax for a Wiki Loves Campaign.']
        );
        errors.push(i18nStrings['Please check your selections and try again.']);
    }

    // Metadata (Depicts / Captions) - FIXED to only check the actual metadata checkboxes
    var depictsChecked = $('#depicts_metadata').is(':checked');
    var captionsChecked = $('#captions_metadata').is(':checked');
    var metadataTypesAreValid = depictsChecked || captionsChecked;

   if (!metadataTypesAreValid) {
    errors.push(
        i18nStrings['Please select at least one type from the Metadata to collect section']
        || 'Please select at least one metadata type (Depicts or Captions).'
    );
}


    // Date range validation
    if (!isValidDateRange()) {
        errors.push('Start date must be earlier than or equal to the end date.');
    }

    // If errors exist → block submit
    if (errors.length > 0) {
        ev.preventDefault();
        showFormErrors(errors);
        return;
    }

    // Inject category data & allow submit
    $('#categories-data')[0].value = JSON.stringify(categorySelections);
});


$('#campaign_type').on("change", function () {
    isWikiLovesCampaign = this.checked;

    if (isWikiLovesCampaign) {
        validateWikiLovesCategories();
    } else {
        clearWikiLovesValidation();
    }
});