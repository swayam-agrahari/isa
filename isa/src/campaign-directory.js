
/*********** Campaign directory page ***********/

// Important: initialize after DOM ready so the global $.ajaxSetup CSRF hook
// (defined in templates/main/layout.html) is installed before DataTables sends POST.
$(document).ready(function () {

    var campaignTableI18nOptions = JSON.parse($('.hidden-i18n-text').text());

    // Hidden booleanStatusColumn is used internally to hide/show closed campaigns
    // This allows filtering the same way regardless of UI language setting
    var booleanStatusColumn = [8];

    // Campaign description, for searching purposes
    var campaignDescColumn = [9];

    var campaignTable = $('#campaign_table').DataTable({
        processing: true,
        serverSide: true,
        responsive: true,
        pageLength: 10,
        ajax: {
            url: '/api/campaigns',
            type: 'POST',
            data: function (d) {
                // Send only the minimal fields we need (keeps request small)
                var order0 = (d.order && d.order.length) ? d.order[0] : null;
                return {
                    draw: d.draw,
                    start: d.start,
                    length: d.length,
                    search_value: (d.search && d.search.value) ? d.search.value : '',
                    order_col: order0 ? order0.column : 0,
                    order_dir: order0 ? order0.dir : 'asc',
                    show_archived: $('#show-closed-campaigns-checkbox').prop('checked') ? 1 : 0
                };
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
            {
                targets: [0],
                responsivePriority: 1
            },
            {
                targets: [-1],
                responsivePriority: 2,
                searchable: false
            },
            {
                targets: booleanStatusColumn,
                visible: false
            },
            {
                targets: campaignDescColumn,
                visible: false
            }
        ],

        // Translation text extracted from hidden HTML element
        language: campaignTableI18nOptions,

        // See https://stackoverflow.com/questions/32252616/ for explanation of dom setting below
        // It's used to get the button in the same line as the other table controls in the header
        dom: "f" +
            "<'row'<'col-sm-12'tr>>" +
            "<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>"
    });

    $('#show-closed-campaigns-checkbox').change(function () {
        // Reload from server; the request includes show_archived=0/1
        campaignTable.ajax.reload();
    });

    /* ===== CLICKABLE CAMPAIGN ROWS ===== */

    // Make entire campaign row clickable and navigate to View link
    function bindCampaignRowNavigation() {
        // Ensure we don't accumulate duplicate handlers across redraws
        $('#campaign_table tbody').off('click', 'tr.campaign-row');
        $('#campaign_table tbody').off('keydown', 'tr.campaign-row');

        $('#campaign_table tbody').on('click', 'tr.campaign-row', function (e) {

            // Prevent row navigation when clicking buttons or links inside the row
            if ($(e.target).closest('a, button').length) {
                return;
            }

            var href = $(this).data('href');
            if (href) {
                window.location.href = href;
            }
        });

        // Keyboard accessibility (Enter key)
        $('#campaign_table tbody').on('keydown', 'tr.campaign-row', function (e) {
            if (e.key === 'Enter') {
                var href = $(this).data('href');
                if (href) {
                    window.location.href = href;
                }
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

    // Initial bind + trim
    bindCampaignRowNavigation();
    trimCampaignDescriptions();

    // Re-bind after every DataTable redraw (pagination, search, filter)
    campaignTable.on('draw', function () {
        bindCampaignRowNavigation();
        trimCampaignDescriptions();
    });
});


