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

function setUpAutocompletes() {
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

    forEachElement('.js-question-jump-autocomplete', function(input){
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
            window.location.href = window.location.pathname + '?type=' + council.council_type + '#' + serialiseObject({
                'jump': council.slug
            });
        });
    });

    forEachElement('.js-location-compare-autocomplete', function(input){
        var council_type = input.dataset.council_type;
        var ac = new Awesomplete(
            input,
            {
                list: councils.filter(function(council){
                    if (typeof council_type === "undefined") { return true; }
                    if (council.council_type === council_type) { return true; }
                    return false;
                }).map(function(council) { return council.name; }),
                minChars: 3,
                autoFirst: true
            }
        );

        input.parentNode.addEventListener('awesomplete-selectcomplete', function(data){
            handleCouncilSelection(data.text);
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

    forEachElement('.js-section-council-autocomplete', function(input){
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
            sp.delete('type');
            sp.delete('council');
            sp.append('council', council.slug);
            window.location.href = window.location.pathname + '?' + sp.toString() + '#questions';
        });
    });
}

setUpAutocompletes();

// Function to handle selection from both autocomplete and suggestions
function handleCouncilSelection(councilName) {
    var council = findItem(councils, {'name': councilName});
    var sp = new URLSearchParams(window.location.search);
    var comparisons = sp.getAll('comparisons');

    if (!comparisons.includes(council.slug)) {
        comparisons.push(council.slug);
    }
    sp.delete('comparisons');
    for (comparison of comparisons.values()) {
        sp.append('comparisons', comparison);
    }
    window.location.href = window.location.pathname + '?' + sp.toString() + '#questions';
}

// Handling suggestion clicks
forEachElement('.js-council-compare-suggestions', function(suggestion) {
    suggestion.addEventListener('click', function(event) {
        event.preventDefault();
        var councilSlug = this.dataset.slug;
        var council = findItem(councils, {'slug': councilSlug}); // Get the council by slug
        handleCouncilSelection(council.name); // Pass the name to the selection handler
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
        window.location.href = window.location.pathname + '?' + sp.toString() + '#questions';
        return false;
    });
});

function sortTableByColumn(columnHeader, direction) {
    var table = columnHeader.closest('table');
    var sortSection = columnHeader.getAttribute('data-sort-section');

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

    forEachElement(table, '[data-sort-section="' + sortSection + '"]', function(el){
        el.classList.add('is-sorted-' + direction);
        el.setAttribute('title', strings[direction]);
    });

    var tbody = table.querySelector('tbody');
    var rows = tbody.querySelectorAll('tbody tr');
    var rowsArr = Array.from(rows);
    var selector = '[data-sort-section="' + sortSection + '"]';
    rowsArr.sort(function(rowA, rowB){
        var sortingCellA = rowA.querySelector(selector);
        var sortingCellB = rowB.querySelector(selector);

        // Sort rows without a relevant cell to the bottom.
        if (direction === 'descending') {
            if (sortingCellA === null) return 1;
            if (sortingCellB === null) return -1;
        } else { 
            if (sortingCellA === null) return -1;
            if (sortingCellB === null) return 1;
        }

        var rawValueA = sortingCellA.getAttribute('data-sort-value');
        var rawValueB = sortingCellB.getAttribute('data-sort-value');

        // Sort NA rows together.
        if (rawValueA === "NA" && rawValueB === "NA") return 0;

        // Sort NA rows to the bottom.
        if (direction === 'descending') {
            if (rawValueA === "NA") return 1;
            if (rawValueB === "NA") return -1;
        } else {
            if (rawValueA === "NA") return -1;
            if (rawValueB === "NA") return 1;
        }

        // Normal numeric comparison
        var valueA = parseFloat(rawValueA);
        var valueB = parseFloat(rawValueB);
        return valueB - valueA;
    }).forEach(function(row){
        if ( direction == 'descending' ) {
            tbody.insertBefore(row, tbody.childNodes[tbody.length]);
        } else {
            tbody.insertBefore(row, tbody.childNodes[0]);
        }
    });
}

function setUpTableSorting() {
    forEachElement('.js-sort-table', function(el){
        el.addEventListener('click', function(){
            if ( this.classList.contains('is-sorted-descending') ) {
                sortTableByColumn(this, 'ascending');
            } else if ( this.classList.contains('is-sorted-ascending') ) {
                // Get the *first* default sortable button, and sort by that.
                var defaultSortColumn = this.closest('table').querySelector('[data-sort-default]');
                var defaultSortDirection = defaultSortColumn.getAttribute('data-sort-default');
                sortTableByColumn(defaultSortColumn, defaultSortDirection);
            } else {
                sortTableByColumn(this, 'descending');
            }
        });
    });
}

setUpTableSorting();

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

if (document.getElementById('display-complete-content')) {
    document.getElementById('display-complete-content').addEventListener('change', function(){
        if ( this.checked ) {
            forEachElement('.js-hidden-toggle', function(trigger){
                var content = document.querySelector('#' + trigger.getAttribute('aria-controls'));
                trigger.setAttribute('aria-expanded', 'true');
                content.removeAttribute('hidden');
            });
        } else {
            forEachElement('.js-hidden-toggle', function(trigger){
                var content = document.querySelector('#' + trigger.getAttribute('aria-controls'));
                trigger.setAttribute('aria-expanded', 'false');
                content.setAttribute('hidden', 'true');
            });
        }
    });
}

forEachElement('#expand-all-sections', function(el){
    el.addEventListener('change', function(){
        if ( this.checked ) {
            document.querySelector('table.table-question-council').classList.remove('accordion-enabled');
        } else {
            document.querySelector('table.table-question-council').classList.add('accordion-enabled');
        }
    });
});

forEachElement('[data-question-type]', function(trigger){
    trigger.addEventListener('click', function(){
        var questionType = trigger.getAttribute('data-question-type');
        var container = document.querySelector('.js-dynamic-content');
        container.setAttribute('data-active-question-type', questionType);
        document.querySelectorAll('[data-question-type].active').forEach(function(el){
            el.classList.remove('active');
        });
        trigger.classList.add('active');
    });
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

// Previous year comparison dropdown on home page
var comparisonYearSelect = document.getElementById('js-comparison-year-select');
if (comparisonYearSelect) {
    comparisonYearSelect.addEventListener('change', showOrHideYearDifference);
    showOrHideYearDifference();
}

function showOrHideYearDifference() {
    var comparisonYearSelect = document.getElementById('js-comparison-year-select');
    if (comparisonYearSelect) {
        var showDifference = comparisonYearSelect.value !== 'hide-year-difference';

        forEachElement('[data-comparison-year]', function(cell) {
            cell.classList.toggle('is-comparison-hidden', cell.getAttribute('data-comparison-year') !== comparisonYearSelect.value);
        });

        forEachElement('.js-previous-year-difference-header', function(header) {
            header.setAttribute('colspan', showDifference ? '2' : '1');
        });

        var sectionsHeaderLabel = document.querySelector('.scorecard-table__sections-header th');
        if (sectionsHeaderLabel) {
            sectionsHeaderLabel.setAttribute('rowspan', showDifference ? '2' : '1');
        }

        forEachElement('.scorecard-table-wrapper', function(element){
            element.classList[ showDifference ? 'add' : 'remove' ]('with-year-difference');
        });
    }
}

// Mobile category selector for Homepage table
function setUpMobileCategorySelect() {
    forEachElement('.js-category-select', function(categorySelect) {
        const announcementElement = document.querySelector('.js-category-select-announcement');
        const tableElement = document.querySelector('.scorecard-table');

        categorySelect.addEventListener('change', function() {
            const selectedValue = this.value;
            const selectedText = this.options[this.selectedIndex].text;

            tableElement.setAttribute('data-section', selectedValue);

            if (announcementElement) {
                announcementElement.textContent = 'Now showing: ' + selectedText;
            }
        });
    });
}
setUpMobileCategorySelect();

function ajaxLoadPageFragments(url) {
    const selectors = [
      '#main-filter',
      '.scorecard-table',
      '.js-category-select-form',
      '.question-performance'
    ];

    document.documentElement.classList.add('loading-shimmer');

    fetch(url)
      .then(response => response.text())
      .then(html => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");

        selectors.forEach(selector => {
          const newElement = doc.querySelector(selector);
          const currentElement = document.querySelector(selector);
          if (newElement && currentElement) {
            currentElement.replaceWith(newElement);
          }
        });

        document.documentElement.classList.remove('loading-shimmer');

        setUpTableSorting();
        showOrHideYearDifference();
        setUpMobileCategorySelect();
        setUpAutocompletes();
        setUpImprovedWorsenedCouncilCheckboxes();

        const advancedFilter = document.querySelector('#advancedFilter');
        if (advancedFilter) {
          new bootstrap.Collapse(advancedFilter, {
            toggle: false
          });
        }
      })
      .catch(err => {
        window.location.href = url;
      });
}

function handleFilterChange(e) {
    e.preventDefault();
    
    const mainForm = document.getElementById('main-filter');
    if (!mainForm) return;
    const formData = new FormData(mainForm);
    
    // Convert FormData to URLSearchParams
    const params = new URLSearchParams(formData);
    
    // Get the base URL (current path without query parameters)
    const baseUrl = window.location.pathname;
    const url = `${baseUrl}?${params.toString()}`;
    history.pushState({}, '', url);

    ajaxLoadPageFragments(url);
}

if (typeof window.fetch !== 'undefined') {
    document.addEventListener('click', e => {
      if (e.target.matches('#council-type-filter a')) {
        e.preventDefault();
        const href = e.target.href;
        history.pushState({}, '', href);
        ajaxLoadPageFragments(href);
      }
    });

    // Handle form submission (Apply filters button)
    document.addEventListener('submit', e => {
      if (e.target.matches('#main-filter')) {
        handleFilterChange(e);
      }
    });

    // Handle radio buttons and select changes
    document.addEventListener('change', e => {
      if (e.target.matches('#main-filter input[type="radio"]') ||
          e.target.matches('#main-filter select')) {
        handleFilterChange(new Event('submit'));
      }
    });

    // Handle reset button
    document.addEventListener('click', e => {
      if (e.target.matches('#resetButton')) {
        e.preventDefault();

        const mainForm = document.getElementById('main-filter');
        if (mainForm) {
          // Reset radio buttons
          mainForm.querySelectorAll('input[type="radio"]').forEach(radio => {
            radio.checked = radio.defaultChecked;
          });

          // Reset select elements
          mainForm.querySelectorAll('select').forEach(select => {
            select.selectedIndex = 0;
          });

          handleFilterChange(new Event('submit'));
        }
      }
    });

    const councilTypePaths = [
      '/',
      '/scoring/district/',
      '/scoring/county/',
      '/scoring/combined/',
      '/scoring/northern-ireland/'
    ];

    window.addEventListener('popstate', e => {
      const url = new URL(window.location.href);
      if (councilTypePaths.includes(url.pathname)) {
        ajaxLoadPageFragments(window.location.href);
      }
    });
}

// Graphics click tracking
var trackEvent = function(eventName, params, callback){
    params = params || {};
    callback = callback || function(){};
    params['event_callback'] = callback;
    setTimeout(callback, 2000);
    gtag('event', eventName, params);
};

document.querySelectorAll('.js-social-graphic-download').forEach(function(el) {
    el.addEventListener('click', function(e) {
        e.preventDefault();
        var eventName = "download";
        var params = {
            url: el.getAttribute('href')
        };

        trackEvent(eventName, params, function(){
            window.location.href = el.href;
        });
    });
});

// Question display improved or worsened councils
// Function to update table visibility based on checkbox states
function updateTableVisibility() {
    var improvedChecked = document.querySelector('.js-checkbox-improved-councils').checked;
    var worsenedChecked = document.querySelector('.js-checkbox-worsened-councils').checked;
    
    // If no checkboxes are checked, show all rows
    var showAll = !improvedChecked && !worsenedChecked;
    
    // Update visibility for rows with year-difference-status
    forEachElement('tr[year-difference-status]', function(row) {
        var status = row.getAttribute('year-difference-status');
        
        // Show the row if:
        // 1. No filters are active (show all)
        // 2. The row's status matches the active filter
        if (showAll || 
            (improvedChecked && status === 'improved') || 
            (worsenedChecked && status === 'worsened')) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function setUpImprovedWorsenedCouncilCheckboxes() {
    forEachElement('.js-checkbox-improved-councils', function(checkbox) {
        checkbox.addEventListener('change', function() {
            // If this checkbox is checked, uncheck the other one
            if (this.checked) {
                forEachElement('.js-checkbox-worsened-councils', function(otherCheckbox) {
                    otherCheckbox.checked = false;
                });
            }
            updateTableVisibility();
        });
    });

    forEachElement('.js-checkbox-worsened-councils', function(checkbox) {
        checkbox.addEventListener('change', function() {
            // If this checkbox is checked, uncheck the other one
            if (this.checked) {
                forEachElement('.js-checkbox-improved-councils', function(otherCheckbox) {
                    otherCheckbox.checked = false;
                });
            }
            updateTableVisibility();
        });
    });
}

setUpImprovedWorsenedCouncilCheckboxes();

// GRAPHS

// Helper so the graphs inside a modal don't break
function wrapChartLabel(label) {
    var maxLength = 28;
    if (label.length <= maxLength) { return label; }
    var lines = [];
    var line = '';
    label.split(' ').forEach(function(word) {
        if (line && (line + ' ' + word).length > maxLength) {
            lines.push(line);
            line = word;
        } else {
            line = line ? line + ' ' + word : word;
        }
    });
    lines.push(line);
    return lines;
}

/*
Turn any <table class="js-chart"> into a Chart.js bar chart.
When no JS is a table instead.
//
Table attributes:
  data-chart-direction="y"  horizontal bars (default), "x" for vertical
  data-chart-preheading     small line above the title
  data-row-height           height per bar in px (default 60)
Title comes from the <caption>, labels from each row's <th>,
values from the first <td>, colour from each row's data-color.
*/

function makeChart(table) {
    var labels = [];
    var datasets = [];
    var rowColors = [];

    // One dataset per <thead>
    var headers = table.querySelectorAll('thead th');
    for (var i = 1; i < headers.length; i++) {
        datasets.push({
            label: headers[i].textContent.trim(),
            data: [],
            backgroundColor: headers[i].getAttribute('data-color') || '#1e7bb0'
        });
    }

    forEachElement(table, 'tbody tr', function(row) {
        labels.push(wrapChartLabel(row.querySelector('th').textContent.trim()));
        forEachElement(row, 'td', function(cell, index) {
            var value = parseFloat(cell.textContent);
            datasets[index].data.push(isNaN(value) ? null : value);
        });
        rowColors.push(row.getAttribute('data-color'));
    });

    if (datasets.length === 1) {
        datasets[0].backgroundColor = rowColors.map(function(color) {
            return color || datasets[0].backgroundColor;
        });
    }

    var caption = table.querySelector('caption');
    var title = caption ? caption.textContent.trim() : '';
    var preheading = table.getAttribute('data-chart-preheading') || '';
    var direction = table.getAttribute('data-chart-direction') || 'y';
    var valueAxis = (direction === 'y') ? 'x' : 'y';
    var rowHeight = parseInt(table.getAttribute('data-row-height') || 60, 10);

    var wrapper = document.createElement('div');
    wrapper.className = 'chart-wrapper';
    wrapper.style.position = 'relative';
    wrapper.style.height = (rowHeight * labels.length + 120) + 'px';

    var canvas = document.createElement('canvas');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', title + ' bar chart');
    wrapper.appendChild(canvas);

    table.parentNode.insertBefore(wrapper, table);
    table.classList.add('visually-hidden');

    var scales = {};
    scales[valueAxis] = {
        min: 0,
        max: 100,
        ticks: {
            callback: function(value) { return value + '%'; }
        }
    };
    scales[direction] = {
        grid: { display: false }
    };

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            indexAxis: direction,
            maintainAspectRatio: false,
            animation: false,
            scales: scales,
            plugins: {
                legend: { display: datasets.length > 1, position: 'bottom' },
                title: {
                    display: preheading !== '',
                    text: preheading,
                    align: 'start',
                    font: { size: 14, weight: 'normal' },
                    padding: { bottom: 2 }
                },
                subtitle: {
                    display: title !== '',
                    text: title,
                    align: 'start',
                    font: { size: 18, weight: 'bold' },
                    padding: { bottom: 16 }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) { return context.dataset.label + ': ' + Math.round(context.raw) + '%'; }
                    }
                }
            }
        }
    });
}

function setUpCharts() {
    if (typeof Chart === 'undefined') { return; }
    forEachElement('.js-chart', function(table) {
        // Charts in a modal are built when it opens, as hidden elements have no size
        var modal = table.closest('.modal');
        if (modal) {
            modal.addEventListener('shown.bs.modal', function() {
                makeChart(table);
            }, { once: true });
        } else {
            makeChart(table);
        }
    });
}

setUpCharts();
