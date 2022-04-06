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

    $('.js-select-text-on-click').on('click', function(){
        if ( window.getSelection && document.createRange ) {
            var selection = window.getSelection();
            if ( selection.toString() == '' ) {
                var element = $(this)[0];
                window.setTimeout(function(){
                    range = document.createRange();
                    range.selectNodeContents(element);
                    selection.removeAllRanges();
                    selection.addRange(range);
                }, 1);
            }
        }
    });
});

var shouldShowInterstitial = function() {
    if ( ! window.localStorage ) {
        // Can’t trigger interstitial, because no localStorage support.
        return false;
    }
    if ( localStorage.getItem('submitted-interstitial-timestamp') ) {
        // Browser has already submitted the interstitial.
        return false;
    }
    if ( localStorage.getItem('skipped-interstitial-timestamp') ) {
        // Respect skipped interstitials for 7 days.
        var skippedTimestamp = localStorage.getItem('skipped-interstitial-timestamp');
        var nowTimestamp = (new Date()).getTime() / 1000;
        var coolingOffPeriod = 60 * 60 * 24 * 7;
        if ( nowTimestamp - skippedTimestamp < coolingOffPeriod ) {
            return false;
        }
    }
    return true;
}

var handleInterstitialTrigger = function(){
    if ( shouldShowInterstitial() ) {
        localStorage.removeItem('skipped-interstitial-timestamp');
        localStorage.setItem('show-interstitial-on-next-pageload', '1');
    }
};

$('form[data-show-interstitial]').on('submit', handleInterstitialTrigger);

$('a[data-show-interstitial]').on('click', handleInterstitialTrigger);

if ( window.localStorage && localStorage.getItem('show-interstitial-on-next-pageload') ) {
    $('#interstitial-modal').on('shown.bs.modal', function(e){
        $('#interstitial-modal [data-toggle="tooltip"]').tooltip();
        if ( window.localStorage ) {
            localStorage.removeItem('show-interstitial-on-next-pageload');
        }
    }).on('hide.bs.modal', function(e){
        if ( window.localStorage ) {
            if ( ! localStorage.getItem('submitted-interstitial-timestamp') ) {
                var timestamp = (new Date()).getTime() / 1000;
                localStorage.setItem('skipped-interstitial-timestamp', timestamp);
            }
        }
    }).modal('show');
}

$('#interstitial-audience-survey').on('change', 'input', function(e){
    var $label = $('label[for="' + $(this).attr('id') + '"]');
    trackEvent('survey_response', {
        survey_question: 'audience',
        survey_answer: $.trim($label.text())
    });
});

$('a[data-show-feedback-modal]').on('click', function(e){
    e.preventDefault();
    $('#data-downloaded').val(e.currentTarget.href);
    $('#data-feedback-modal').modal('show');
});

$('#data-feedback-modal').on('hide.bs.modal', function(e){
    download = $('#data-downloaded').val();
    if (download) {
        window.location = download;
    }
});

$('#data-feedback-modal').on('keydown', function(e){
    if (e.originalEvent.key == 'Escape') {
        $('#data-downloaded').val('');
    }
});

$('#feedback-email').on('keyup change', function(){
    var hasProvidedEmail = $(this).val() && $(this).is(':valid');
    if ( hasProvidedEmail ) {
        $('#feedback-submit').removeClass('btn-secondary').addClass('btn-primary').attr('disabled', null);
    } else {
        $('#feedback-submit').addClass('btn-secondary').removeClass('btn-primary').attr('disabled', true);
    }
})

$('form[data-ajax-feedback-submit]').on('submit', function(e){
    e.preventDefault();
    var $form = $(this);

    $form.parents('.modal').modal('hide');

    $.ajax({
        method: $form.attr('method'),
        url: $form.attr('action'),
        data: $form.serialize()
    });
});

$('.conditional-fields').each(function(){
    var $conditional = $(this);
    var $prevInput = $(this).prev().find('input');

    $conditional.parent().on('change', function(){
        console.log('change', $prevInput[0].checked);
        $conditional.toggleClass('d-none', ! $prevInput[0].checked);
        $conditional.find('input').eq(0).focus();
    });
});

$('form[data-ajax-submit]').on('submit', function(e){
    e.preventDefault();
    var $form = $(this);

    if ( $form.parents('.modal').length ) {
        // Assume we’re in an interstitial. Record submission, then close.
        if ( window.localStorage ) {
            var timestamp = (new Date()).getTime() / 1000;
            localStorage.setItem('submitted-interstitial-timestamp', timestamp);
        }
        $form.parents('.modal').modal('hide');
    }

    $.ajax({
        method: $form.attr('method'),
        url: $form.attr('action'),
        data: $form.serialize()
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

$('.details-accordion').on('click', function(){
    $(this).siblings('.details-accordion[open]').removeAttr('open');
});

$('.scorecard-table').each(function(){
    var $table = $(this);
    var $btn = $('<button>');
    $btn.text('Show more');
    $btn.on('click', function(){
        if ( $table.is('.open') ) {
            $table.removeClass('open');
            $btn.text('Show more');
        } else {
            $table.addClass('open');
            $btn.text('Show less');
        }
    });
    $btn.appendTo($table);
});

$('.nzlh-landing-page').on('click', 'a[href]', function(e){
    var href = $(e.currentTarget).attr('href');

    var callback;
    if (
        e.ctrlKey ||
        e.shiftKey ||
        e.metaKey ||
        (e.button && e.button == 1) // middle mouse button
    ){
        callback = function() {};
    } else {
        e.preventDefault();
        callback = function() {
            if (href) {
                window.location.href = href;
            }
        };
    }

    var text = $(e.currentTarget).text().replace(/\s+/g, ' ').replace(/(^\s+|\s+$)/g, '') || $(e.currentTarget).find('[src]').attr('src');

    trackEvent('nzlh_landing_page_click', {
        'link_text': text,
        'destination': href
    }).done(callback);
});
