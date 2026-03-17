"use strict";

django.jQuery(function ($) {
  if (modemUpgraderSchema === null) {
    return;
  }
  var modemImageChanged = false;

  // Intercept form submission to show power-off warning
  $("form").on("submit", function (e) {
    var imageField = $("#id_devicemodemfirmware-0-image");
    if (!imageField.length || !imageField.val()) {
      return true;
    }
    // Only warn if the image was changed (new firmware assignment)
    if (!modemImageChanged) {
      return true;
    }
    if (!$(this).data("modem-upgrade-confirmed")) {
      e.preventDefault();
      var confirmed = confirm(
        "⚠️ WARNING: Do NOT power OFF the device until the modem firmware upgrade is complete.\n\n" +
        "Powering off during upgrade may permanently damage the modem.\n\n" +
        "Do you want to proceed with the modem firmware upgrade?"
      );
      if (confirmed) {
        $(this).data("modem-upgrade-confirmed", true);
        $(this).submit();
      }
      return false;
    }
  });
  // Do not render JSONSchema form if the image field is not changed.
  // The "change" event is also emitted when the form is rendered.
  // The "modemImageChanged" variable is used as flag to prevent this
  // behavior.
  if (
    $("#id_devicemodemfirmware-0-upgrade_options").val() &&
    $("#id_devicemodemfirmware-0-upgrade_options").val() !== "null"
  ) {
    modemImageChanged = true;
  }
  $("#devicemodemfirmware-group").on(
    "change",
    "#id_devicemodemfirmware-0-image",
    function (event) {
      if (!$(event.target).val()) {
        $("#id_devicemodemfirmware-0-upgrade_options_jsoneditor").hide();
        return;
      }
      $("#id_devicemodemfirmware-0-upgrade_options_jsoneditor").show();
      if (modemImageChanged) {
        django._loadJsonSchemaUi(
          $("#id_devicemodemfirmware-0-upgrade_options").get(0),
          false,
          modemUpgraderSchema,
          true,
        );
      } else {
        modemImageChanged = true;
      }
    },
  );
  $("#devicemodemfirmware-group .add-row a").click(function () {
    modemImageChanged = true;
  });
});
