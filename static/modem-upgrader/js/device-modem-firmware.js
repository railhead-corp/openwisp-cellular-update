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
  var upgradeOptionsObserver = null;

  function disableUpgradeOptionsInputs(container) {
    container.querySelectorAll("input, textarea").forEach(function (el) {
      el.setAttribute("disabled", "disabled");
      el.setAttribute("readonly", "readonly");
    });
    // Handle <select> elements via Select2 jQuery API
    // (setAttribute readonly is invalid for <select> — only disabled works)
    container.querySelectorAll("select").forEach(function (el) {
      el.setAttribute("disabled", "disabled");
      $(el).prop("disabled", true).trigger("change.select2");
      el.style.pointerEvents = "none";
      el.style.cursor = "not-allowed";
    });
  }

  function makeUpgradeOptionsReadOnly() {
    var container = document.getElementById(
      "id_devicemodemfirmware-0-upgrade_options_jsoneditor"
    );
    if (!container) return;
    disableUpgradeOptionsInputs(container);
    // Use MutationObserver to re-disable any elements JSONEditor re-renders
    if (upgradeOptionsObserver) upgradeOptionsObserver.disconnect();
    upgradeOptionsObserver = new MutationObserver(function () {
      disableUpgradeOptionsInputs(container);
    });
    upgradeOptionsObserver.observe(container, { childList: true, subtree: true });
  }

  function pollAndDisableUpgradeOptions(maxAttempts, interval) {
    var attempts = 0;
    var timer = setInterval(function () {
      attempts++;
      var container = document.getElementById(
        "id_devicemodemfirmware-0-upgrade_options_jsoneditor"
      );
      if (container && container.querySelectorAll("input, select, textarea").length > 0) {
        makeUpgradeOptionsReadOnly();
        clearInterval(timer);
      } else if (attempts >= maxAttempts) {
        clearInterval(timer);
      }
    }, interval);
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
        try {
          django._loadJsonSchemaUi(
            $("#id_devicemodemfirmware-0-upgrade_options").get(0),
            false,
            modemUpgraderSchema,
            true,
          );
        } catch (e) {
          console.warn("JSONEditor failed to initialize:", e);
        }
        // Poll until JSONEditor finishes rendering, then disable all inputs
        // (runs even if JSONEditor threw an error)
        pollAndDisableUpgradeOptions(20, 200);
      } else {
        modemImageChanged = true;
      }
    },
  );
  // Also disable on page load if options are already rendered
  $(document).ready(function () {
    console.log("Checking if upgrade options need to be disabled on page load...");
    pollAndDisableUpgradeOptions(20, 200);
  });
  $("#devicemodemfirmware-group .add-row a").click(function () {
    modemImageChanged = true;
  });
});
