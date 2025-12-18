$(document).ready(function () {
    /* 1. i18n Parsing with Safety */
    var campaignTableI18nOptions = {};
    try {
        var i18nRaw = $('.hidden-i18n-text').text().trim();
        if (i18nRaw) {
            campaignTableI18nOptions = JSON.parse(i18nRaw);
        }
    } catch (e) {
        campaignTableI18nOptions = {};
    }

    var booleanStatusColumn = [8];
    var campaignDescColumn = [9];

    /* 2. DataTable Initialization */
    var campaignTable = $('#campaign_table').DataTable({
        processing: true,
        serverSide: true,
        responsive: true,
        pageLength: 10,
        ajax: {
            url: '/api/campaigns',
            type: 'GET',
            data: function (d) {
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

    /* 3. Event Listeners & Redraw logic */
    $('#show-closed-campaigns-checkbox').change(function () {
        campaignTable.ajax.reload();
    });

    function bindCampaignRowNavigation() {
        $('#campaign_table tbody').off('click', 'tr.campaign-row');
        $('#campaign_table tbody').on('click', 'tr.campaign-row', function (e) {
            if ($(e.target).closest('a, button').length) return;
            var href = $(this).data('href');
            if (href) window.location.href = href;
        });
    }

    function trimCampaignDescriptions() {
        var MAX_LENGTH = 120;
        $('#campaign_table .campaign-description').each(function () {
            var text = $(this).text().trim();
            if (text.length > MAX_LENGTH) $(this).text(text.substring(0, MAX_LENGTH) + '...');
        });
    }

    bindCampaignRowNavigation();
    trimCampaignDescriptions();
    campaignTable.on('draw', function () {
        bindCampaignRowNavigation();
        trimCampaignDescriptions();
    });
});