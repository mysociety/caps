function isVisible(el) {
    return (el.offsetParent !== null)
};

function forEachElement(arg1, arg2, arg3) {
    var context = (typeof arg3 == 'function') ? arg1 : document;
    var selector = (typeof arg3 == 'function') ? arg2 : arg1;
    var callback = (typeof arg3 == 'function') ? arg3 : arg2;

    var elements = context.querySelectorAll(selector);
    Array.prototype.forEach.call( elements, callback );
};

function findItem(list, params) {
    var key = Object.keys(params)[0];
    var val = Object.values(params)[0];
    for ( var i=0; i < list.length; i++ ) {
        if ( list[i][key] == val ) {
            return list[i];
        }
    }
    return null;
};

function siblingIndex(el) {
    var index = 0;
    while ( (el=el.previousElementSibling) != null ) {
        ++index;
    }
    return index;
}

function serialiseObject(obj) {
    return Object.keys(obj).map(function(key){
        return '' + encodeURIComponent(key) + '=' + encodeURIComponent(obj[key]);
    }).join('&');
};

function unserialiseObject(string) {
    var obj = {};
    var vars = string.split('&');
    for (var i = 0; i < vars.length; i++) {
        var pair = vars[i].split('=');
        obj[ decodeURIComponent(pair[0]) ] = decodeURIComponent(pair[1]);
    }
    return obj;
};

function updateUIFromHashState(){
    var state_string = window.location.hash.substring(1); // remove the leading "#" character
    var state = unserialiseObject(state_string);

    if ( state.jump ) {
        jump(state.jump);
    }
};

function jump(slug) {
    forEachElement('[data-jump-slug="' + slug + '"]', function(el){
        if ( isVisible( el ) ) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            forEachElement('[data-jump-slug].highlight', function(el){
                el.classList.remove('highlight');
            });
            el.classList.add('highlight');
        }
    });
}

// Apply state from the hash
updateUIFromHashState();

// Monitor for future changes of the hash state
window.addEventListener('hashchange', updateUIFromHashState);

forEachElement('.js-location-search-autocomplete', function(input){
    var ac = new Awesomplete(
        input,
        {
            list: councils.map(function(council){
                return council.name;
            }),
            minChars: 3,
            autoFirst: true
        }
    );
    input.parentNode.addEventListener('awesomplete-select', function(data){
        data.preventDefault();
        var council = findItem(councils, {'name': data.text });
        window.location.href = council['council_url'];
    });
    input.placeholder = 'Council name or postcode';
});

forEachElement('.js-location-jump-autocomplete', function(input){
    var ac = new Awesomplete(
        input,
        {
            list: councils.map(function(council){
                return council.name;
            }),
            minChars: 3,
            autoFirst: true
        }
    );
    input.parentNode.addEventListener('awesomplete-selectcomplete', function(data){
        var council = findItem(councils, {'name': data.text });
        window.location.href = council.scoring_url + '#' + serialiseObject({
            'jump': council.slug
        });
    });
});

forEachElement('.js-location-compare-autocomplete', function(input){
    var ac = new Awesomplete(
        input,
        {
            list: councils.map(function(council){
                return council.name;
            }),
            minChars: 3,
            autoFirst: true
        }
    );
    input.parentNode.addEventListener('awesomplete-selectcomplete', function(data){
        var council = findItem(councils, {'name': data.text });
        var sp = new URLSearchParams(window.location.search)
        var comparisons = sp.getAll('comparisons');

        if (!comparisons.includes(council.slug)) {
            comparisons.push(council.slug);
        }
        sp.delete('comparisons');
        for (comparison of comparisons.values()) {
            sp.append('comparisons', comparison);
        }
        window.location.href = window.location.pathname + '?' + sp.toString();
    });
});

forEachElement('.js-comparison-council', function(link){
    link.addEventListener('click', function(data){
        data.preventDefault();
        var slug = this.getAttribute('data-slug');

        var sp = new URLSearchParams(window.location.search)
        var comparisons = sp.getAll('comparisons');
        comparisons = comparisons.filter(comparison => comparison != slug);
        sp.delete('comparisons');
        for (comparison of comparisons.values()) {
            sp.append('comparisons', comparison);
        }
        window.location.href = window.location.pathname + '?' + sp.toString();
        return false;
    });
});

var navbarButton = document.getElementById("navbar-toggler");
var navbarContent = document.getElementById("navbarSupportedContent");
navbarButton.addEventListener('click', function(){
    if(!navbarContent.classList.contains('show-height')) {
        navbarContent.classList.toggle('show-height');
        navbarContent.style.height = "auto";
        let height = navbarContent.clientHeight + "px";
        navbarContent.style.height = "0px";
        setTimeout(function(){
            navbarContent.style.height = height;
        }, 0);
    } else {
        navbarContent.style.height = "0px";
        navbarContent.addEventListener('transitionend', function(){
            navbarContent.classList.remove('show-height');
        }, {once: true})
    }
});

function sortTableByColumn(columnHeader, direction) {
    var table = columnHeader.closest('table');
    var headerCell = columnHeader.closest('th');
    var columnIndex = siblingIndex(headerCell);

    // Values here are labels for what will happen
    // when you click, not the current state!
    var strings = {
        'none': 'Sort highest first',
        'descending': 'Sort lowest first',
        'ascending': 'Cancel sorting',
    }

    forEachElement(table, '.js-sort-table', function(el){
        el.classList.remove('is-sorted-descending');
        el.classList.remove('is-sorted-ascending');
        el.setAttribute('title', strings['none']);
    });

    columnHeader.classList.add('is-sorted-' + direction);
    columnHeader.setAttribute('title', strings[direction]);

    var tbody = table.querySelector('tbody');
    var rows = tbody.querySelectorAll('tbody tr');
    var rowsArr = Array.from(rows);
    rowsArr.sort(function(rowA, rowB){
        var valueA = parseFloat( rowA.children[columnIndex].getAttribute('data-sort-value') );
        var valueB = parseFloat( rowB.children[columnIndex].getAttribute('data-sort-value') );
        return valueB - valueA;
    }).forEach(function(row){
        if ( direction == 'descending' ) {
            tbody.insertBefore(row, tbody.childNodes[tbody.length]);
        } else {
            tbody.insertBefore(row, tbody.childNodes[0]);
        }
    });
}

forEachElement('.js-sort-table', function(el){
    el.addEventListener('click', function(){
        if ( this.classList.contains('is-sorted-descending') ) {
            sortTableByColumn(this, 'ascending');
        } else if ( this.classList.contains('is-sorted-ascending') ) {
            var defaultSortColumn = this.closest('table').querySelector('[data-sort-default]');
            var defaultSortDirection = defaultSortColumn.getAttribute('data-sort-default');
            sortTableByColumn(defaultSortColumn, defaultSortDirection);
        } else {
            sortTableByColumn(this, 'descending');
        }
    });
});

// Display modals
forEachElement('.popup-trigger', function(trigger){
    trigger.addEventListener('click', function(){
        var popupTrigger = trigger.getAttribute('data-popup-trigger');
        var popupModal = document.querySelector('[data-popup-modal="' + popupTrigger + '"]');
        popupModal.classList.add('is--visible');

        popupModal.querySelector('.popup-modal__close').addEventListener('click', function(){
            popupModal.classList.remove('is--visible');
        });
    });
});

forEachElement('.js-toggle-council-question-table-section', function(trigger){
    var table = trigger.closest('table');
    var thisTbody = trigger.closest('tbody');

    table.classList.add('accordion-enabled');

    trigger.addEventListener('click', function(){
        if ( thisTbody.classList.contains('open') ) {
            thisTbody.classList.remove('open');
        } else {
            forEachElement(table, 'tbody.open', function(tbody){
                tbody.classList.remove('open');
            });
            thisTbody.classList.add('open');
        }
        thisTbody.scrollIntoView({ behavior: 'smooth' });
    });
});

forEachElement('.js-collapse-children', function(wrapper){
    var children = Array.prototype.slice.call(wrapper.children);

    if ( children.length > 1 ) {
        var details = document.createElement('details');
        var summary = document.createElement('summary');
        summary.textContent = 'Show more';
        details.appendChild(summary);

        for ( var i=1; i < children.length; i++ ) {
            details.appendChild(children[i]);
        }

        wrapper.appendChild(details);
    }
});

forEachElement('.sticky-in-page-nav > button', function(button){
    button.addEventListener('click', function(){
        button.setAttribute( 'aria-expanded', (button.getAttribute('aria-expanded') == 'true') ? 'false' : 'true' );
    });
});

// Example (no aria-expanded, so controlled element will start off hidden):
//     <button class="js-hidden-toggle" aria-controls="foobar">…</button>
//     <div id="foobar">This will start off hidden</div>
// Can add aria-expanded=true to make controlled element start off visible:
//     <button class="js-hidden-toggle" aria-controls="foobar" aria-expanded="true">…</button>
//     <div id="foobar">This will start off visible</div>
forEachElement('.js-hidden-toggle', function(trigger){
    var content = document.querySelector('#' + trigger.getAttribute('aria-controls'));
    var expanded = trigger.getAttribute('aria-expanded');
    var updateUI = function(){
        var expanded = trigger.getAttribute('aria-expanded');
        if (expanded == 'true') {
            content.removeAttribute('hidden');
        } else {
            content.setAttribute('hidden', 'true');
        }
    };

    // Hide controlled element, at page load, unless aria-expanded="true"
    if ( expanded != 'true' ) {
        trigger.setAttribute('aria-expanded', 'false');
    }
    updateUI();

    // Toggle controlled element on click
    trigger.addEventListener('click', function(){
        var expanded = trigger.getAttribute('aria-expanded');
        trigger.setAttribute( 'aria-expanded', (expanded == 'true') ? 'false' : 'true' );
        updateUI();
    });
});

document.getElementById('display-complete-content').addEventListener('change', function(){
    if ( this.checked ) {
        forEachElement('.section-question-heading .js-hidden-toggle', function(trigger){
            var content = document.querySelector('#' + trigger.getAttribute('aria-controls'));
            trigger.setAttribute('aria-expanded', 'true');
            content.removeAttribute('hidden');
        });
    } else {
        forEachElement('.section-question-heading .js-hidden-toggle', function(trigger){
            var content = document.querySelector('#' + trigger.getAttribute('aria-controls'));
            trigger.setAttribute('aria-expanded', 'false');
            content.setAttribute('hidden', 'true');
        });
    }
});

forEachElement('[data-methodology-switch-council-type]', function(trigger){
    trigger.addEventListener('click', function(){
        var councilType = trigger.getAttribute('data-methodology-switch-council-type');
        var container = document.querySelector('.js-dynamic-content');
        container.setAttribute('data-methodology-active-council-type', councilType);
        forEachElement('.js-methodology-council-autocomplete', function(input){
            input.value = '';
        });
    });
});

forEachElement('.js-methodology-council-autocomplete', function(input){
    var ac = new Awesomplete(
        input,
        {
            list: councils.map(function(council){
                return council.name;
            }),
            minChars: 3,
            autoFirst: true
        }
    );
    input.parentNode.addEventListener('awesomplete-selectcomplete', function(data){
        var council = findItem(councils, {'name': data.text });
        console.log(council);
        var container = document.querySelector('.js-dynamic-content');
        container.setAttribute('data-methodology-active-council-type', council.council_type);
    });
});
