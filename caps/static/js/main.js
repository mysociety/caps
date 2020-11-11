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

});
