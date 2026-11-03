// Fase 10 (E10.1): token CSRF de la sesión (meta "csrf-token" de base.html) en las escrituras de la consola.
// - Solicitudes HTMX (hx-post, hx-put, hx-delete): cabecera X-CSRF-Token en htmx:configRequest.
// - Formularios POST nativos: campo oculto csrf_token al enviarse.
// El servidor decide siempre: sin token válido la escritura se rechaza (403).
(function () {
  "use strict";
  function token() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : null;
  }
  document.addEventListener("htmx:configRequest", function (evento) {
    var valor = token();
    var verbo = (evento.detail.verb || "get").toLowerCase();
    if (valor && verbo !== "get") { evento.detail.headers["X-CSRF-Token"] = valor; }
  });
  document.addEventListener("submit", function (evento) {
    var formulario = evento.target;
    if (!(formulario instanceof HTMLFormElement)) { return; }
    if ((formulario.getAttribute("method") || "get").toLowerCase() !== "post") { return; }
    var valor = token();
    if (!valor || formulario.querySelector('input[name="csrf_token"]')) { return; }
    var campo = document.createElement("input");
    campo.type = "hidden";
    campo.name = "csrf_token";
    campo.value = valor;
    formulario.appendChild(campo);
  }, true);
})();
