document.addEventListener("htmx:responseError", function (event) {
  const box = document.getElementById("request-error");
  box.textContent = event.detail.xhr.status === 403
    ? "No tienes permiso para consultar estos datos."
    : "No pudimos actualizar los resultados. Intenta nuevamente o recarga la página.";
  box.classList.remove("d-none");
  box.focus();
});
document.addEventListener("htmx:sendError", function () {
  const box = document.getElementById("request-error");
  box.textContent = "No hay conexión con el servidor. Revisa tu conexión e intenta nuevamente.";
  box.classList.remove("d-none");
  box.focus();
});
document.addEventListener("htmx:beforeRequest", function () {
  document.getElementById("request-error").classList.add("d-none");
});
