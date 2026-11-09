/* Shared camera/image UI adapter; QR identity is always checked by Django. */
(function (root) {
  "use strict";
  function bind({modal, camera, fileReader, fileInput, status, onResult, startButton = null, stopButton = null}) {
    function failure(error) {
      const value = String(error?.name || "") + " " + String(error);
      let message = "No se reconoció un QR. Prueba otra imagen o escribe el código manualmente.";
      if (/NotAllowed|Permission|denied/i.test(value)) message = "Permiso de cámara denegado. Puedes habilitarlo en el navegador, usar una imagen o escribir el código.";
      else if (/NotFound|DevicesNotFound|Overconstrained/i.test(value)) message = "No se encontró una cámara compatible. Usa una imagen o escribe el código.";
      else if (/NotReadable|TrackStart|busy/i.test(value)) message = "La cámara está ocupada o no pudo iniciarse. Cierra otras aplicaciones y vuelve a intentarlo.";
      status(message);
    }
    if (!root.Html5Qrcode || !root.BitacoraQR) {
      status("No se pudo cargar el lector. Puedes buscar el código manualmente.");
      return {stop() {}};
    }
    const controller = root.BitacoraQR.createController({
      makeReader: mode => new root.Html5Qrcode(mode === "camera" ? camera.id : fileReader.id, {
        formatsToSupport: [root.Html5QrcodeSupportedFormats.QR_CODE], verbose: false
      }),
      onResult: text => {
        camera.hidden = true;
        status("QR leído. Consultando el equipo…");
        onResult(text);
      },
      onError: failure,
      onReady: () => status("Cámara activa. Coloca el QR completo dentro de la imagen."),
      releaseMedia: () => {
        modal.querySelectorAll("video").forEach(video => {
          video.srcObject?.getTracks().forEach(track => track.stop());
        });
      }
    });
    function stop() {
      camera.hidden = true;
      return controller.stop();
    }
    function start() {
      if (!root.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        status("La cámara requiere HTTPS o localhost y un navegador compatible. Usa una imagen o escribe el código.");
        return;
      }
      camera.hidden = false;
      status("Solicitando acceso a la cámara…");
      controller.start();
    }
    if (startButton) startButton.addEventListener("click", start);
    else modal.addEventListener("shown.bs.modal", start);
    if (stopButton) stopButton.addEventListener("click", () => {
      stop();
      status("Cámara detenida. Puedes volver a escanear o usar una imagen.");
    });
    modal.addEventListener("hide.bs.modal", stop);
    fileInput.addEventListener("change", event => {
      const file = event.target.files[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024 || !["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
        stop();
        status("Selecciona una imagen PNG, JPG o WebP de hasta 10 MB.");
        event.target.value = "";
        return;
      }
      camera.hidden = true;
      status("Leyendo imagen…");
      controller.file(file);
      event.target.value = "";
    });
    root.addEventListener("pagehide", stop);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        stop();
        root.bootstrap.Modal.getInstance(modal)?.hide();
      }
    });
    return {stop};
  }
  root.BitacoraScanner = {bind};
  const form = document.getElementById("scan-form");
  if (!form) return;
  const scanner = bind({
    modal: document.getElementById("camera-modal"),
    camera: document.getElementById("camera-reader"),
    fileReader: document.getElementById("file-reader"),
    fileInput: document.getElementById("qr-file"),
    status(text) {
      document.getElementById("scan-status").textContent = text;
      document.getElementById("camera-status").textContent = text;
    },
    onResult(text) {
      form.elements.query.value = text;
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", scanner.stop);
})(window);
