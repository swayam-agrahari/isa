
var i18nStrings = JSON.parse($('.hidden-i18n-text').text());

function getCampaignId () {
    var parts = window.location.pathname.split("/");
    return parseInt(parts[parts.length - 2]);
}

var campaign_id = getCampaignId();

$.getJSON( "../../api/get-campaign-graph-stats-data?campaign=" + campaign_id )
    .done( function( response ) {
        var contributors_stats_data_points = response[ 0 ],
            conuntry_stats_data_points = response[ 1 ];
        var contributor_pie_chart = new CanvasJS.Chart( "contributorChartContainer", {
            animationEnabled: true,
            title:{
                text: i18nStrings["Contributor Stats"]
            },
            axisX:{
                interval: 1
            },
            axisY2:{
                interlacedColor: "rgba(1,77,101,.2)",
                gridColor: "rgba(1,77,101,.1)"
            },
            data: [ {
                type: "pie",
                startAngle: 45,
                indexLabel: "{label} ({y})",
                yValueFormatString:"#,##0.#"%"",
                dataPoints: contributors_stats_data_points
            } ]
        } );

        var country_pie_chart = new CanvasJS.Chart( "countryChartContainer", {
            animationEnabled: true,

            title:{
                text: i18nStrings["Country Stats"]
            },
            axisX:{
                interval: 1
            },
            axisY2:{
                interlacedColor: "rgba(1,77,101,.2)",
                gridColor: "rgba(1,77,101,.1)"
            },
            data: [{
                type: "pie",
                startAngle: 30,
                indexLabel: "{label} ({y})",
                yValueFormatString:"#,##0.#"%"",
                dataPoints: conuntry_stats_data_points
            }]
        } );
        // We render the pie charts now
        contributor_pie_chart.render();
        country_pie_chart.render();
    } );