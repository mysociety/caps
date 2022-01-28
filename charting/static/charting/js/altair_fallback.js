
function blob2canvas(canvas, blob) {
    var img = new window.Image();
    img.addEventListener("load", function () {
        canvas.getContext("2d").drawImage(img, 0, 0);
    });
    img.setAttribute("src", blob);
}

var supportsES6 = function () {
    try {
        new Function("(a = 0) => a");
        return true;
    }
    catch (err) {
        return false;
    }
}();

var embed_opt = { "mode": "vega-lite", "actions": { "export": false, "source": false, "compiled": false, "editor": false }, "scaleFactor": 2 };

async function toClipboardPrint(el, view, spec) {
    // copy the current chart to the clipboard
    // rescales and sizes for print ratio
    el.querySelector('details').removeAttribute('open');

    el = document.createElement("div");
    el.setAttribute("id", "screenshot_div");
    document.body.appendChild(el)
    el.style.width = "20cm";
    el.style.height = "10cm";
    spec["height"] = "container";

    results = await vegaEmbed("#" + el.id, spec, embed_opt);
    view = results.view;

    base64data = await view.toImageURL('png', 3);

    fetch(base64data)
        .then(res => {
            return res.blob();
        })
        .then(blob => {
            navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
            el.remove();
        });
    
}

async function toClipboard(el, view, spec, data_source, logo_src) {
    // copy the current chart to the clipboard, with logo and url
    // resizes for twitter ratio
    width = 1020
    height = 517
    scaleFactor = 3
    footer = 200

    if (data_source == "") {
        data_source = "Source: " + window.location
    }

    el.querySelector('details').removeAttribute('open');

    el = document.createElement("div");
    el.setAttribute("id", "screenshot_div");
    document.body.appendChild(el)
    el.style.width = width + "px";
    height = el.clientWidth / (16 / 9);
    el.style.height = (height - Math.ceil(footer / scaleFactor)) + "px";
    spec["height"] = "container";
    results = await vegaEmbed("#" + el.id, spec, embed_opt);
    view = results.view;
    base64data = await view.toImageURL('png', 3);

    // add mysociety logo at bottom
    source_canvas = el.querySelector("canvas")
    new_canvas = document.createElement("CANVAS");
    document.body.appendChild(new_canvas)

    new_canvas.style.width = width * scaleFactor + "px"
    new_canvas.style.height = height * scaleFactor + "px"
    new_canvas.width = width * scaleFactor
    new_canvas.height = height * scaleFactor
    ctx = new_canvas.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, new_canvas.width, new_canvas.height);

    var img = new Image();
    img.onload = function () {
        ctx.drawImage(this, 0, 0, new_canvas.width, new_canvas.height - footer);
    };
    img.src = base64data;

    var logo = new Image();
    logo.setAttribute("crossorigin", "anonymous")
    logo.onload = function () {
        ratio = logo.height / logo.width;
        left = width * scaleFactor * 0.8;
        length = width * scaleFactor * 0.2;
        height = length * ratio;
        ctx.drawImage(this, 0, new_canvas.height - height, length, height);

        ctx.font = "40px Lato";
        ctx.fillStyle = 'black';
        text_width = ctx.measureText(data_source + "   ").width;
        ctx.fillText(data_source, new_canvas.width - text_width, new_canvas.height - 50);
        base64data = new_canvas.toDataURL(1)

        fetch(base64data)
            .then(res => {
                return res.blob();
            })
            .then(blob => {
                navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
                el.remove();
                new_canvas.remove();
            });


    };
    logo.src = logo_src;
}