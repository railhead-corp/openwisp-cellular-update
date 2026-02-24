/**
 * JavaScript for modem batch upgrade confirmation page
 */

(function($) {
    'use strict';

    $(document).ready(function() {
        // Initialize upgrade options widget if present
        if (typeof modemUpgraderSchema !== 'undefined' && modemUpgraderSchema) {
            // Schema is available for validation
            console.log('Modem upgrader schema loaded:', modemUpgraderSchema);
        }

        // Handle cancel button
        $('.cancel-link').on('click', function(e) {
            e.preventDefault();
            window.history.back();
        });
    });

})(django.jQuery);
