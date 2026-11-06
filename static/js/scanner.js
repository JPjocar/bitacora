(function () {
  "use strict";
  const form = document.getElementById("scan-form");
  if (!form) return;
  const modal = document.getElementById("camera-modal");
  function status(text) {
    document.getElementById("scan-status").textContent = text;
    document.getElementById("camera-status").textContent = text;
  }
  function failure(error) {
    const value = String(error?.name || "") + " " + String(error);
    let message = "No se reconoció un QR. Prueba otra imagen o escribe el código manualmente.";
    if (/NotAllowed|Permission|denied/i.test(value)) message = "Permiso de cámara denegado. Puedes habilitarlo en el navegador, usar una imagen o escribir el código.";
    else if (/NotFound|DevicesNotFound|Overconstrained/i.test(value)) message = "No se encontró una cámara compatible. Usa una imagen o escribe el código.";
    else if (/NotReadable|TrackStart|busy/i.test(value)) message = "La cámara está ocupada o no pudo iniciarse. Cierra otras aplicaciones y vuelve a intentarlo.";
    status(message);
  }
  if (!window.Html5Qrcode || !window.BitacoraQR) {
    status("No se pudo cargar el lector. Puedes buscar el código manualmente.");
    return;
  }
  const controller = window.BitacoraQR.createController({
    makeReader: mode => new Html5Qrcode(mode === "camera" ? "camera-reader" : "file-reader", {
      formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE], verbose: false
    }),
    onResult: text => {
      status("QR leído. Consultando el equipo…");
      form.elements.query.value = text;
      // Submit to our server for validation; decoded text is never a navigation target.
      form.requestSubmit();
    },
    onError: failure,
    onReady: () => status("Cámara activa. Coloca el QR completo dentro de la imagen."),
    releaseMedia: () => {
      modal.querySelectorAll("video").forEach(video => {
        video.srcObject?.getTracks().forEach(track => track.stop());
      });
    }
  });
  modal.addEventListener("shown.bs.modal", () => {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      status("La cámara requiere HTTPS o localhost y un navegador compatible. Usa una imagen o escribe el código.");
      return;
    }
    status("Solicitando acceso a la cámara…");
    controller.start();
  });
  modal.addEventListener("hide.bs.modal", () => { controller.stop(); });
  document.getElementById("qr-file").addEventListener("change", event => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024 || !["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      controller.stop();
      status("Selecciona una imagen PNG, JPG o WebP de hasta 10 MB.");
      event.target.value = "";
      return;
    }
    status("Leyendo imagen…");
    controller.file(file);
    event.target.value = "";
  });
  form.addEventListener("submit", () => { controller.stop(); });
  window.addEventListener("pagehide", () => { controller.stop(); });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      controller.stop();
      bootstrap.Modal.getInstance(modal)?.hide();
    }
  });
})();
