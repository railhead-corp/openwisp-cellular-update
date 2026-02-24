/* Modem Build Admin JavaScript */
(function($) {
    'use strict';
    
    $(document).ready(function() {
        // Handle modem build form interactions
        console.log('Modem Build admin loaded');
        
        // OS identifier field handling
        var osIdentifierField = $('#id_os_identifier');
        if (osIdentifierField.length) {
            osIdentifierField.on('change', function() {
                console.log('OS identifier changed:', $(this).val());
            });
        }
        
        // Category field handling
        var categoryField = $('#id_category');
        if (categoryField.length) {
            categoryField.on('change', function() {
                console.log('Category changed:', $(this).val());
            });
        }
    });
})(django.jQuery);
