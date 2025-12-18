/*********** Campaign directory page ***********/

$(document).ready(function () {
    console.log("ISA Debug: Initializing Campaign Directory JS");

    /* 1. i18n Parsing with Safety and Logging */
    var campaignTableI18nOptions = {};
    try {
        var i18nElement = $('.hidden-i18n-text');
        console.log("ISA Debug: Found i18n element:", i18nElement.length > 0);
        
        var i18nRaw = i18nElement.text().trim();
        if (i18nRaw) {
            campaignTableI18nOptions = JSON.parse(i18nRaw);
            console.log("ISA Debug: i18n JSON parsed successfully");
        } else {
            console.warn("ISA Debug: i18n element is empty");
        }
    } catch (e) {
        console.error("ISA Debug: DataTables i18n parsing failed. Error:", e);
        console.error("ISA Debug: Raw text that failed to parse:", $('.hidden-i18n-text').text());
        // Fallback to defaults so the script doesn't stop
        campaignTableI18nOptions = {};
    }

    var booleanStatusColumn = [8];
    var campaignDescColumn = [9];

    /* 2. DataTable Initialization */
    console.log("ISA Debug: Starting DataTable initialization");
    
    var campaignTable = $('#campaign_table').DataTable({
        processing: true,
        serverSide: true,
        responsive: true,
        pageLength: 10,
        ajax: {
            url: '/api/campaigns',
            type: 'GET', // Switched to GET to avoid Toolforge CSRF issues
            data: function (d) {
                console.log("ISA Debug: AJAX data callback triggered. Draw:", d.draw);
                var order0 = (d.order && d.order.length) ? d.order[0] : null;
                var params = {
                    draw: d.draw,
                    start: d.start,
                    length: d.length,
                    search_value: (d.search && d.search.value) ? d.search.value : '',
                    order_col: order0 ? order0.column : 0,
                    order_dir: order0 ? order0.dir : 'asc',
                    show_archived: $('#show-closed-campaigns-checkbox').prop('checked') ? 1 : 0
                };
                console.log("ISA Debug: Sending request with params:", params);
                return params;
            },
            dataSrc: function(json) {
                console.log("ISA Debug: Received response from server:", json);
                if (!json.data || json.data.length === 0) {
                    console.warn("ISA Debug: API returned success but 0 records.");
                }
                return json.data;
            },
            error: function (xhr, error, code) {
                console.error("ISA Debug: AJAX Error!");
                console.error("Status:", xhr.status);
                console.error("Response:", xhr.responseText);
                console.error("Error Type:", error);
            }
        },

        columns: [
            { data: 'campaign_html', className: 'ps-4' },
            { data: 'images_html', className: 'text-center' },
            { data: 'participants', className: 'text-center' },
            { data: 'contributions', className: 'text-center' },
            { data: 'start_date' },
            { data: 'end_date_html' },
            { data: 'status_html', className: 'text-center', orderable: false },
            { data: 'actions_html', className: 'pe-4 text-end', orderable: false, searchable: false },
            { data: 'status_flag' },
            { data: 'long_description' }
        ],

        createdRow: function (row, data) {
            $(row)
                .addClass('campaign-row')
                .attr('data-href', data.href)
                .attr('role', 'link')
                .attr('tabindex', '0')
                .css('cursor', 'pointer');
        },

        columnDefs: [
            { targets: [0], responsivePriority: 1 },
            { targets: [-1], responsivePriority: 2, searchable: false },
            { targets: booleanStatusColumn, visible: false },
            { targets: campaignDescColumn, visible: false }
        ],

        language: campaignTableI18nOptions,

        dom: "f" +
            "<'row'<'col-sm-12'tr>>" +
            "<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>"
    });

    console.log("ISA Debug: DataTable object created");

    /* 3. Event Listeners */
    $('#show-closed-campaigns-checkbox').change(function () {
        console.log("ISA Debug: Archived toggle changed. Reloading table...");
        campaignTable.ajax.reload();
    });

    function bindCampaignRowNavigation() {
        $('#campaign_table tbody').off('click', 'tr.campaign-row');
        $('#campaign_table tbody').off('keydown', 'tr.campaign-row');

        $('#campaign_table tbody').on('click', 'tr.campaign-row', function (e) {
            if ($(e.target).closest('a, button').length) return;
            var href = $(this).data('href');
            if (href) {
                console.log("ISA Debug: Navigating to:", href);
                window.location.href = href;
            }
        });

        $('#campaign_table tbody').on('keydown', 'tr.campaign-row', function (e) {
            if (e.key === 'Enter') {
                var href = $(this).data('href');
                if (href) window.location.href = href;
            }
        });
    }

    function trimCampaignDescriptions() {
        var MAX_LENGTH = 120;
        $('#campaign_table .campaign-description').each(function () {
            var text = $(this).text().trim();
            if (text.length > MAX_LENGTH) {
                $(this).text(text.substring(0, MAX_LENGTH) + '...');
            }
        });
    }

    // Initial triggers
    bindCampaignRowNavigation();
    trimCampaignDescriptions();

    // Redraw trigger
    campaignTable.on('draw', function () {
        console.log("ISA Debug: Table draw event completed.");
        bindCampaignRowNavigation();
        trimCampaignDescriptions();
    });
});