"use strict";

django.jQuery(function ($) {
  if (modemUpgraderSchema === null) {
    return;
  }
  var modemImageChanged = false;
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
