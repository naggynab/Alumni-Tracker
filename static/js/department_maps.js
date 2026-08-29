(function () {
    "use strict";

    var dataElement = document.getElementById("department-map-data");
    if (!dataElement || typeof L === "undefined") return;

    var data = JSON.parse(dataElement.textContent || "{}");
    var numberFormat = new Intl.NumberFormat();

    function escapeHtml(value) {
        return String(value == null ? "" : value).replace(/[&<>'"]/g, function (character) {
            return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[character];
        });
    }

    function popupContent(point, label) {
        return "<strong>" + escapeHtml(point.location) + "</strong>" +
            "<div>" + label + ": <b>" + numberFormat.format(point.count) + "</b></div>" +
            "<div>Share of records: <b>" + point.percentage + "%</b></div>";
    }

    function tooltipContent(point, label) {
        return "<span>" + escapeHtml(label) + "</span>" +
            "<strong>" + escapeHtml(point.location) + "</strong>" +
            "<span>" + (label === "Country" ? "Alumni" : "Students") +
            ": <b>" + numberFormat.format(point.count) + "</b></span>";
    }

    function markerColor(point, largest) {
        var ratio = largest ? Math.sqrt(point.count / largest) : 0;
        var red = Math.round(39 + (224 - 39) * ratio);
        var green = Math.round(120 + (110 - 120) * ratio);
        var blue = Math.round(181 + (95 - 181) * ratio);
        return "rgb(" + red + ", " + green + ", " + blue + ")";
    }

    function renderMap(elementId, points, label, options) {
        var element = document.getElementById(elementId);
        if (!element) return;

        var map = L.map(elementId, {scrollWheelZoom: true, worldCopyJump: true}).setView(options.center, options.zoom);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 18,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        var largest = points.reduce(function (max, point) { return Math.max(max, point.count); }, 0);
        points.forEach(function (point) {
            var color = markerColor(point, largest);
            var scale = 0.88 + (largest ? 0.20 * Math.sqrt(point.count / largest) : 0);
            var icon = L.divIcon({
                className: "distribution-pin-icon",
                html: '<span class="distribution-pin" style="--pin-color:' + color + ";--pin-scale:" + scale + '"><span></span></span>',
                iconSize: [28, 30],
                iconAnchor: [14, 29],
                tooltipAnchor: [0, -15],
                popupAnchor: [0, -24]
            });
            L.marker([point.latitude, point.longitude], {
                icon: icon,
                title: point.location,
                alt: point.location,
                riseOnHover: true,
                bubblingMouseEvents: false
            }).bindTooltip(tooltipContent(point, options.hoverLabel), {
                direction: "top",
                offset: [0, -14],
                className: "distribution-tooltip",
                sticky: true
            }).bindPopup(popupContent(point, label)).addTo(map);
        });

        if (!points.length) {
            var empty = document.createElement("p");
            empty.className = "map-empty";
            empty.textContent = options.emptyMessage;
            element.appendChild(empty);
        }
        window.setTimeout(function () { map.invalidateSize(); }, 100);
    }

    renderMap("alumni-world-map", data.world || [], "Alumni", {
        center: [20, 10],
        zoom: 2,
        hoverLabel: "Country",
        emptyMessage: "No mapped current-country records yet."
    });
    renderMap("nepal-student-map", data.nepal || [], "Students", {
        center: [28.3949, 84.1240],
        zoom: 6,
        hoverLabel: "Location",
        emptyMessage: "No mapped Nepal city or district records yet."
    });
})();
