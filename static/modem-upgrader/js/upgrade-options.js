/* Modem Firmware Upgrade Options JavaScript */
(function() {
    'use strict';
    
    // Basic JSON validation for upgrade options field
    document.addEventListener('DOMContentLoaded', function() {
        const upgradeOptionsFields = document.querySelectorAll('.modem-upgrade-options-field');
        
        upgradeOptionsFields.forEach(function(field) {
            field.addEventListener('blur', function() {
                try {
                    if (field.value.trim()) {
                        JSON.parse(field.value);
                        field.style.borderColor = '';
                    }
                } catch (e) {
                    field.style.borderColor = 'red';
                    console.error('Invalid JSON in upgrade options:', e);
                }
            });
        });
    });
})();
