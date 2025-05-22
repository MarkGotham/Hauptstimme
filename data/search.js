$(document).ready(function () {
    $.fn.dataTable.ext.type.order["movement-pre"] = function (d) {
        // Match the (first) movement number and letter (a, b, etc.) if present
        var match = d.match(/^(\d+)([a-z]?|(?:,\d+)*)$/i);
        if (match) {
            // Parse the (first) movement number
            var number = parseInt(match[1], 10);
            // Extract the movement letter if present
            var letter = match[2] || "";
            // Return the movement number (scaled up) + the ASCII value of the movement letter
            return number * 1000 + (letter.charCodeAt(0) || 0);
        }
        return 0;
    };
    $("#README").DataTable({
        paging: false,
        columnDefs: [
            { "type": "movement", target: 2 }
        ]
    });
});
