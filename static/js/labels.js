"use strict";
const printButton = document.getElementById("print-labels");
if (printButton) {
  Promise.all(Array.from(document.querySelectorAll(".device-label img"), image => image.decode()))
    .then(() => {
      printButton.disabled = false;
      document.getElementById("print-status").textContent = "Etiquetas listas para imprimir.";
    })
    .catch(() => {
      document.getElementById("print-status").textContent = "No se pudieron cargar todos los QR. Recarga antes de imprimir.";
    });
  printButton.addEventListener("click", () => window.print());
}
