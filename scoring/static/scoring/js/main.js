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

var secondaryNavbarButton = document.getElementById("mobile-content-navbar");
var secondaryNavbarContent = document.getElementById("content-navbar");
secondaryNavbarButton.addEventListener('click', function(){
    if(!secondaryNavbarContent.classList.contains('show-height')) {
        secondaryNavbarButton.setAttribute('aria-expanded', true);
        secondaryNavbarButton.classList.toggle('close');
        secondaryNavbarContent.classList.toggle('show-height');
        secondaryNavbarContent.style.height = "auto";
        let height = secondaryNavbarContent.clientHeight + "px";
        secondaryNavbarContent.style.height = "0px";
        setTimeout(function(){
            secondaryNavbarContent.style.height = height;
        }, 0);
    } else {
        secondaryNavbarButton.setAttribute('aria-expanded', false);
        secondaryNavbarButton.classList.remove('close');
        secondaryNavbarContent.style.height = "0px";
        secondaryNavbarContent.addEventListener('transitionend', function(){
            secondaryNavbarContent.classList.remove('show-height');
        }, {once: true})
    }
});

// Open accordion item
let accordionItemData = document.getElementsByClassName('accordion-data');
let accordionItemQuestion = document.getElementsByClassName('accordion-heading');

for (let i = 0; i < accordionItemData.length; i++) {
    let accordionItemDataOffHeight = accordionItemData[i].offsetHeight;
    let accordionItemDataScrollHeight = accordionItemData[i].scrollHeight;
    let buttonAccordion = accordionItemQuestion[i].querySelector('.btn-open-accordion');  
    buttonAccordion.addEventListener('click', () => {
        if(!accordionItemData[i].classList.contains('active')) {
            accordionItemData[i].classList.toggle('active');
            buttonAccordion.classList.toggle('active');
            accordionItemQuestion[i].classList.toggle('active');
            accordionItemData[i].style.height = "auto";
            let height = accordionItemData[i].clientHeight + "px";
            accordionItemData[i].style.height = "0px";
            setTimeout(() => {
                accordionItemData[i].style.height = height;
            }, 0) 
        } else {
            accordionItemData[i].style.height = "0px";
            accordionItemData[i].addEventListener('transitionend', () => {
                accordionItemData[i].classList.remove('active');
                accordionItemQuestion[i].classList.remove('active');
                buttonAccordion.classList.remove('active');
            }, {once: true})
        }
    })
}

// Question display details
const openDetailsbutton = secondaryNavbarButton = document.getElementById('display-complete-content');
const accordionSection = document.getElementById('accordion-sections');
let sectionQuestionContent = document.getElementsByClassName('section-question-content');
let sectionQuestionHeading = document.getElementsByClassName('section-question-heading');
var openedAccordions = document.getElementsByClassName('accordion-data active');
openDetailsbutton.addEventListener('change', (event) => {
    for (let k = 0; k < openedAccordions.length; k++) {
        openedAccordions[k].style.height = "auto";
    };

    if (event.target.checked) {
        accordionSection.classList.toggle('open-details');
        accordionSection.classList.remove('close-details');
        for (let l = 0; l < sectionQuestionContent.length; l++) {
            sectionQuestionContent[l].classList.add('show-height');
            sectionQuestionContent[l].style.height = "auto";
            sectionQuestionContent[l].style.visibility = "visible";
        };
    } else {
        accordionSection.classList.remove('open-details');
        accordionSection.classList.add('close-details');
        for (let l = 0; l < sectionQuestionContent.length; l++) {
            sectionQuestionContent[l].classList.remove('show-height');
            sectionQuestionContent[l].style.height = "0";
            sectionQuestionContent[l].style.visibility = "hidden";
        };
    }
});

for (let j = 0; j < sectionQuestionContent.length; j++) {
    let sectionQuestionButton = sectionQuestionHeading[j].querySelector('.btn-display-question-details');
    let closestAccordion = sectionQuestionButton.closest('.accordion-data');

    sectionQuestionButton.addEventListener('click', () => {
        if(!sectionQuestionContent[j].classList.contains('show-height')) {
            sectionQuestionContent[j].classList.toggle('show-height');
            sectionQuestionContent[j].style.height = "auto";
            let sectionQuestionheight = sectionQuestionContent[j].clientHeight + "px";
            sectionQuestionContent[j].style.height = "0px";
            sectionQuestionContent[j].style.visibility = "hidden";
            setTimeout(() => {
                sectionQuestionContent[j].style.visibility = "visible";
                sectionQuestionContent[j].style.height = sectionQuestionheight;
                closestAccordion.style.height = "auto";
            }, 0);
        } else {
            sectionQuestionContent[j].style.height = "0px";
            sectionQuestionContent[j].style.visibility = "hidden";
            closestAccordion.style.height = "auto";
            sectionQuestionContent[j].classList.remove('show-height');
        }
    })
}

forEachElement('[data-methodology-switch-council-type]', function(trigger){
    trigger.addEventListener('click', function(){
        var councilType = trigger.getAttribute('data-methodology-switch-council-type');
        var container = document.querySelector('.js-dynamic-content');
        container.setAttribute('data-methodology-active-council-type', councilType);
        forEachElement('.js-methodology-council-autocomplete', function(input){
            input.value = '';
        });
    });
})

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
