"use strict";

django.jQuery(function ($) {
    // --- helpers ---

    function updateSubmitButton() {
        // Re-query DOM each time so we always see the live checked state
        var anyChecked =
            $("[name='selected_related_fw_ids']:checked").length > 0 ||
            $("[name='selected_firmwareless_ids']:checked").length > 0;
        $("#upgrade-selected-btn").prop("disabled", !anyChecked);
    }

    function syncSelectAll($toggle) {
        if (!$toggle.length) { return; }
        var name = $toggle.data("target");
        var $boxes = $("[name='" + name + "']");
        var total = $boxes.length;
        var checked = $boxes.filter(":checked").length;
        $toggle[0].indeterminate = (checked > 0 && checked < total);
        $toggle.prop("checked", checked === total);
    }

    // --- event delegation (survives any DOM manipulation by the admin theme) ---

    // "Select / Deselect all" toggle
    $(document).on("change", ".select-all-checkbox", function () {
        var isChecked = $(this).prop("checked");
        $("[name='" + $(this).data("target") + "']").prop("checked", isChecked);
        updateSubmitButton();
    });

    // Individual device checkbox → sync its section's select-all toggle
    $(document).on(
        "change",
        "[name='selected_related_fw_ids'], [name='selected_firmwareless_ids']",
        function () {
            syncSelectAll(
                $(".select-all-checkbox[data-target='" + $(this).attr("name") + "']")
            );
            updateSubmitButton();
        }
    );

    // Cancel / go-back link
    $(document).on("click", ".cancel-link", function (e) {
        e.preventDefault();
        window.history.back();
    });

    // --- initialise states on page load ---
    updateSubmitButton();
    $(".select-all-checkbox").each(function () {
        syncSelectAll($(this));
    });
});
