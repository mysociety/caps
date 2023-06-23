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

    $(".js-copy-text").click(function(){
        window.setTimeout(function(){
            copyText = $(".js-copy-text").siblings('.js-copy-hidden')[0].innerHTML;
            navigator.clipboard.writeText(copyText)
        }, 1);
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

$('.modal-content').on('click', function(e) {
    e.originalEvent.clickedInsideDialog = 1;
});

$('#data-feedback-modal').on('click', function(e){
    if (e.originalEvent.clickedInsideDialog !== 1) {
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

$('form[data-ajax-submit]').on('submit', function(e){
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

$('form[data-ajax-feedback-submit]').on('submit', function(e){
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

var trackEventMP = function(eventName, eventParams) {
    // Custom events don't work in GA4 if you have { analytics_storage: "denied" }
    // (ie: if you have cookies disabled). So we use the Measurement Protocol API
    // to track custom events instead.
    //
    // trackEvent() returns a promise, and resolves it when either the MP API
    // handles our event, or a maximum fallback period elapses. Promises can
    // only be resolved once, so this also ensures whatever callbacks
    // are attached to the promise only execute once.
    //
    // eventName should be a string. eventParams is an optional array of event
    // parameters to be sent to Google Analytics.

    var dfd = $.Deferred();

    var callback = function(){
        dfd.resolve();
    };

    // Returns either an array, or undefined.
    var measurementProtocolDetails = window.dataLayer.filter(function(row){
        return row[0] === 'measurement_protocol_secret';
    })[0];

    if (measurementProtocolDetails) {
        var measurementParams = {
            measurement_id: measurementProtocolDetails[1], // G-XXXXXXXXXX
            api_secret: measurementProtocolDetails[2]
        }
        if (measurementProtocolDetails[3]) {
            var eventParams = $.extend(params, {
                debug_mode: '1'
            });
        }

        // Set a random client_id (2 32-bit integers seperated by a dot).
        // Note this random approach means the GA debugView won't work.
        // (To get that to work, you need to turn back on the cookies,
        // then use the same client_id as in in the _ga cookie.)
        var client_id = Math.floor(Math.random() * 1000000000) + '.' + Math.floor(Math.random() * 1000000000);

        // https://developers.google.com/analytics/devguides/collection/protocol/ga4/sending-events?client_type=gtag#send_an_event
        $.ajax({
            url: 'https://www.google-analytics.com/mp/collect?' + $.param(measurementParams),
            method: 'POST',
            data: JSON.stringify({
                client_id: client_id,
                events: [{
                    name: eventName,
                    params: eventParams
                }]
            })
        }).always(callback);

        // Wait a maximum of 2 seconds for ajax to resolve.
        setTimeout(callback, 2000);

    } else {
        // Measurement Protocol not available. Resolve promise immediately.
        callback();
    }

    return dfd.promise();
};

$('.details-accordion').on('click', function(){
    $(this).siblings('.details-accordion[open]').removeAttr('open');
});

$('.js-show-more-wrapper').each(function(){
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

$('.council-list-filters').each(function(){
    var $form = $(this);
    var $footer = $(this).find('.card-footer');
    var $btn = $('<button>');
    $btn.attr('type', 'button');
    $btn.addClass('btn btn-link py-0');

    var updateUI = function(){
        if ( $form.is('.open') ) {
            $btn.text('Show fewer filters…');
        } else {
            $btn.text('Filter by authority type and more…');
        }
    }

    $btn.on('click', function(){
        $form.toggleClass('open');
        updateUI();
    });

    $btn.appendTo($footer);
    updateUI();
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

$('.sort-by-wrapper #id_sort').on('change', function(){
    var table = $('#council_list'), sort_by = $('.sort-by-wrapper #id_sort').val(), asc = true;
    // update the form so clicking submit to filter retains the search order
    $('#id_sort').val(sort_by);
    if ( sort_by.substring(0,1) == '-' ) {
        sort_by = sort_by.substring(1);
        asc = false;
    }
    var col = $('[data-sortable="' + sort_by + '"]');
    var rows = table.find('tr:gt(0)').toArray().sort(compare_cells(col.index()));
    if (!asc){rows = rows.reverse()}
    // make sure that 0 values are always at the bottom of the list
    var zero_rows = Array();
    for (var i = 0; i < rows.length; i++){
        if (get_value_from_cell(rows[i], col.index()) == '0') {
            zero_rows.push(rows[i]);
        } else {
            table.append(rows[i]);
        }
    }
    for (var i = 0; i < zero_rows.length; i++){
        table.append(zero_rows[i]);
    }
})
function compare_cells(index) {
    return function(a, b) {
        var valA = get_value_from_cell(a, index), valB = get_value_from_cell(b, index);
        return $.isNumeric(valA) && $.isNumeric(valB) ? valA - valB : valA.toString().localeCompare(valB);
    }
}
function get_value_from_cell(row, index){
    return $(row).children('td').eq(index).data('sortvalue');
}

$( '[data-content-navbar-switch]' ).click(function(event) {
    var contentNavbar = this.getAttribute('data-content-navbar-switch');
    var container = document.querySelector('.js-dynamic-content');
    container.setAttribute('data--active-content-navbar', contentNavbar)
    trackEvent('content_navbar_switch', {"content_navbar": contentNavbar})
    // do not follow the link and do not move the position on the screen
    // event.preventDefault();
});

// when we scroll pass the start of a .js-content block, update the active content navbar
$(window).scroll(function() {
    var scrollPosition = $(window).scrollTop();
    // iterate through all js-section and find the one that is closest to the top of the screen
    var closestSection = null;
    var closestSectionDistance = null;
    $('.js-section').each(function() {
        var sectionPosition = $(this).offset().top;
        var distance = Math.abs(sectionPosition - scrollPosition);
        if (closestSectionDistance === null || distance < closestSectionDistance) {
            closestSection = this;
            closestSectionDistance = distance;
        }
    }
    );
    // update the active content navbar
    var contentNavbar = closestSection.getAttribute('id');
    var container = document.querySelector('.js-dynamic-content');
    container.setAttribute('data--active-content-navbar', contentNavbar)

    // update sidebar name
    var headerNamePosition = $('#header-name').offset().top;
    var headerNameHeight = $('#header-name').outerHeight();
    var sidebarTop = $('#sidebar-top');
    var sidebarTopDefaultContent = sidebarTop.attr('data-default-content');
    if (scrollPosition > headerNamePosition + headerNameHeight) {
        $('.sidebar-top').html($('#header-name').html());
    } else {
        $('.sidebar-top').html(sidebarTopDefaultContent);
    }
}
);


