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

        // Intercept upgrade submission to show power-off warning
        $('input[name="upgrade_all"], input[name="upgrade_related"]').on('click', function(e) {
            var confirmed = confirm(
                '⚠️ WARNING: Do NOT power OFF any device until the modem firmware upgrade is complete.\n\n' +
                'Powering off during upgrade may permanently damage the modem.\n\n' +
                'Do you want to proceed with the modem firmware upgrade?'
            );
            if (!confirmed) {
                e.preventDefault();
                return false;
            }
        });

        // Handle cancel button
        $('.cancel-link').on('click', function(e) {
            e.preventDefault();
            window.history.back();
        });
    });

})(django.jQuery);
