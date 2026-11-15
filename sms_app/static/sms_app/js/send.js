/*
 * Send page helpers: live character counter, SMS segment estimate,
 * message preview, and a double-submit guard.
 * Uses textContent only (never innerHTML) so user text can't inject markup.
 */
(function () {
  "use strict";

  var form = document.getElementById("sms-form");
  var phone = document.getElementById("id_phone_number");
  var message = document.getElementById("id_message");
  if (!form || !phone || !message) { return; }

  var charCount = document.getElementById("char-count");
  var segmentCount = document.getElementById("segment-count");
  var encodingNote = document.getElementById("encoding-note");
  var counter = charCount.parentElement;
  var previewTo = document.getElementById("preview-to");
  var previewBody = document.getElementById("preview-body");
  var sendBtn = document.getElementById("send-btn");
  var maxLength = parseInt(message.getAttribute("maxlength"), 10) || 480;

  // GSM-7 basic character set and its extension table (extension chars cost 2).
  var GSM_BASIC = "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡" +
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
  var GSM_EXTENDED = "^{}\\[~]|€\f";

  function estimate(text) {
    var septets = 0;
    var gsm = true;
    for (var i = 0; i < text.length; i++) {
      var ch = text.charAt(i);
      if (GSM_BASIC.indexOf(ch) !== -1) { septets += 1; }
      else if (GSM_EXTENDED.indexOf(ch) !== -1) { septets += 2; }
      else { gsm = false; break; }
    }
    if (gsm) {
      return { segments: septets <= 160 ? (septets ? 1 : 0) : Math.ceil(septets / 153), gsm: true };
    }
    var units = text.length; // UTF-16 code units, which is how UCS-2 counts them
    return { segments: units <= 70 ? 1 : Math.ceil(units / 67), gsm: false };
  }

  function update() {
    var text = message.value;
    var info = estimate(text);

    charCount.textContent = text.length;
    segmentCount.textContent = info.segments + (info.segments === 1 ? " segment" : " segments");
    encodingNote.textContent = text.length === 0 ? "" :
      (info.gsm ? "(standard characters)" : "(special characters/emoji - shorter segments)");
    counter.classList.toggle("over", text.length >= maxLength);

    var number = phone.value.trim();
    previewTo.textContent = number || "—";

    if (text.trim()) {
      previewBody.textContent = text;
      previewBody.classList.remove("placeholder");
    } else {
      previewBody.textContent = "Your message will appear here.";
      previewBody.classList.add("placeholder");
    }
  }

  phone.addEventListener("input", update);
  message.addEventListener("input", update);

  // Prevent accidental double-sends (which would cost double).
  form.addEventListener("submit", function () {
    sendBtn.disabled = true;
    sendBtn.textContent = "Sending...";
  });
  // Re-enable if the user navigates back to this page.
  window.addEventListener("pageshow", function () {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send SMS";
  });

  update();
})();
