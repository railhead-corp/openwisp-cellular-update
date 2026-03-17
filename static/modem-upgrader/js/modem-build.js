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

        // Client-side .bin file validation for firmware image uploads
        function validateBinFile(input) {
            var $input = $(input);
            var fileName = input.files && input.files[0] ? input.files[0].name : '';
            // Remove any previous client-side error
            $input.closest('.form-row, .field-file, td, div').find('.bin-validation-error').remove();
            if (fileName && !fileName.toLowerCase().endsWith('.bin')) {
                // Clear the file input
                $input.val('');
                // Show inline error message next to the input
                var errorHtml = '<ul class="errorlist bin-validation-error">' +
                    '<li>Only .bin firmware files are allowed.</li></ul>';
                $input.after(errorHtml);
                // Also show an alert so users can't miss it
                alert('Invalid file: "' + fileName + '"\n\nOnly .bin firmware files are allowed.');
            }
        }

        // Bind to existing file inputs
        $(document).on('change', 'input[type="file"][name$="-file"]', function() {
            validateBinFile(this);
        });
    });
})(django.jQuery);
