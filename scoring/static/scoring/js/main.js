function isVisible(el) {
    return (el.offsetParent !== null)
};

function forEachElement(selector, callback) {
    var elements = document.querySelectorAll(selector);
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
