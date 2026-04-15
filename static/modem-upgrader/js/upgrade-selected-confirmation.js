/**
 * JavaScript for modem batch upgrade confirmation page
 */

(function($) {
    'use strict';

    function updateSelectedCount() {
        var count = $('input.device-checkbox:checked').length;
        var $btn = $('#upgrade-selected-btn');
        var $info = $('#selected-count-info');
        if (count > 0) {
            $btn.prop('disabled', false);
            $info.text(count + ' device(s) selected');
        } else {
            $btn.prop('disabled', true);
            $info.text('');
        }
    }

    $(document).ready(function() {
        // Initialize upgrade options widget if present
        if (typeof modemUpgraderSchema !== 'undefined' && modemUpgraderSchema) {
            console.log('Modem upgrader schema loaded:', modemUpgraderSchema);
        }

        // Update button state whenever a checkbox changes
        $(document).on('change', 'input.device-checkbox', function() {
            updateSelectedCount();
        });

        // Select all for a group
        $(document).on('click', '.select-all-link', function(e) {
            e.preventDefault();
            var group = $(this).data('group');
            $('input.' + group + '-device-checkbox').prop('checked', true);
            updateSelectedCount();
        });

        // Deselect all for a group
        $(document).on('click', '.deselect-all-link', function(e) {
            e.preventDefault();
            var group = $(this).data('group');
            $('input.' + group + '-device-checkbox').prop('checked', false);
            updateSelectedCount();
        });

        // Warn before submitting
        $(document).on('click', '#upgrade-selected-btn', function(e) {
            var confirmed = confirm(
                '⚠️ WARNING: Do NOT power OFF any device until the modem firmware upgrade is complete.\n\n' +
                'Powering off during upgrade may permanently damage the modem.\n\n' +
                'Do you want to proceed with the modem firmware upgrade for the selected devices?'
            );
            if (!confirmed) {
                e.preventDefault();
                return false;
            }
        });

        // Handle cancel button
        $(document).on('click', '.cancel-link', function(e) {
            e.preventDefault();
            window.history.back();
        });

        // Set initial button state
        updateSelectedCount();
    });

})(django.jQuery);
