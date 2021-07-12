$(function() {
    if( 'geolocation' in navigator ) {
        $('.js-geolocate').removeClass('d-none');
        $('.js-geolocate a').on('click', function(e){
            e.preventDefault();
            var $a = $(this);
            var $icon = $a.find('.js-geolocate-icon');
            var $spinner = $a.find('.js-geolocate-spinner');

            $icon.addClass('d-none');
            $spinner.removeClass('d-none');

            navigator.geolocation.getCurrentPosition(function(position){
                var params = {
                    lon: position.coords.longitude.toFixed(6),
                    lat: position.coords.latitude.toFixed(6)
                };
                window.location = $a.attr('href') + '?' + $.param(params);
            }, function(err){
                if (err.code === 1) {
                    var text = 'You declined location sharing.';
                } else {
                    var text = 'Your location could not be found.'
                }
                var $p = $('<p>').attr({
                    role: 'alert',
                    class: 'mb-0 text-muted'
                }).text(text);
                $a.replaceWith($p);
            }, {
                enableHighAccuracy: true,
                timeout: 10000
            });
        })
    }

    // Returns an array `numberOfPoints` long, where the final item
    // is `radius`, and all the other items are 0.
    var pointRadiusFinalDot = function(numberOfPoints, radius){
        var pointRadius = [];
        for (var i=1; i < numberOfPoints; i++) {
            pointRadius.push(0);
        }
        pointRadius.push(radius);
        return pointRadius;
    };

    var makeSparkline = function makeSparkline($el, valuesStr, color){
        var values = [];
        var labels = [];
        $.each(valuesStr.split(' '), function(key, value){
            if ( value.trim() !== '' ) {
                values.push(Number(value));
                labels.push('');
            }
        });
        var spread = Math.max.apply(null, values) - Math.min.apply(null, values);

        if ( typeof color === 'undefined' && 'getComputedStyle' in window ) {
            color = window.getComputedStyle($el[0]).getPropertyValue('color');
        }

        return new Chart($el, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    pointRadius: pointRadiusFinalDot(values.length, 2),
                    pointBackgroundColor: color,
                    borderColor: color,
                    borderWidth: 2,
                    lineTension: 0,
                    backgroundColor: 'transparent'
                }]
            },
            options: {
                layout: {
                    padding: {
                        top: 2,
                        right: 3,
                        bottom: 2,
                        left: 3
                    }
                },
                scales: {
                    xAxes: [{
                        type: "category",
                        display: false
                    }],
                    yAxes: [{
                        type: "linear",
                        display: false,
                        ticks: {
                            min: Math.min.apply(null, values) - (spread * 0.3),
                            max: Math.max.apply(null, values) + (spread * 0.3)
                        }
                    }]
                },
                legend: {
                    display: false
                },
                animation: {
                    duration: 0
                },
                tooltips: {
                    enabled: false
                },
                title: {
                    display: false
                }
            }
        });
    };

    $('.js-sparkline canvas').each(function() {
        makeSparkline(
            $(this),
            $(this).data('values'),
            $(this).data('color')
        );
    });

    $('a[data-plan-id]').on("click", function(e) {
        var link = $(this);
        var link_url = link.attr('href');
        var link_text = link.text();
        var link_ext = "." + link_url.split('.').pop();
        var file_name = link_url.split('/').pop();
        var council_slug = link.data("council-slug");
        var plan_id = link.data("plan-id");

        // Set up callback to open link in current window,
        // if user hasn't initiated click with modifier keys.
        var callback;
        if (
            e.ctrlKey ||
            e.shiftKey ||
            e.metaKey ||
            (e.button && e.button == 1) // middle mouse button
        ){
            callback = function(){}
        } else {
            e.preventDefault();
            callback = function(){
                window.location.href = link_url;
            }
        }

        trackEvent('plan_link_click', {
            file_extension: link_ext,
            file_name: file_name,
            link_url: link_url,
            link_text: link_text,
            council_slug: council_slug,
            plan_id: plan_id
        }).done(callback);
    });
});

$('#interstitial-modal').on('shown.bs.modal', function(e){
    $('#interstitial-modal [data-toggle="tooltip"]').tooltip();
}).modal('show');

$('.conditional-fields').each(function(){
    var $conditional = $(this);
    var $prevInput = $(this).prev().find('input');

    $conditional.parent().on('change', function(){
        console.log('change', $prevInput[0].checked);
        $conditional.toggleClass('d-none', ! $prevInput[0].checked);
        $conditional.find('input').eq(0).focus();
    });
});

var trackEvent = function(eventName, params) {
    // We'll return a promise, and resolve it when either Gtag handles
    // our event, or a maximum fallback period elapses. Promises can
    // only be resolved once, so this also ensures whatever callbacks
    // are attached to the promise only execute once.
    var dfd = $.Deferred();

    var callback = function(){
        dfd.resolve();
    };

    // Tell Gtag to resolve our promise when it's done.
    var params = $.extend(params, {
        event_callback: callback
    });

    gtag('event', eventName, params);

    // Wait a maximum of 2 seconds for Gtag to resolve promise.
    setTimeout(callback, 2000);

    return dfd.promise();
};
