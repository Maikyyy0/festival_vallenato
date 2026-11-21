/* Panel de datos: consulta la API JSON y dibuja los gráficos sin librerías
 * externas. Todo el texto se inserta con textContent (nunca innerHTML) para
 * evitar inyección de HTML desde los datos. */
(function () {
  "use strict";

  var raiz = document.getElementById("panel");
  if (!raiz) return;

  var URL_RESUMEN = raiz.dataset.urlResumen;
  var URL_RESULTADOS = raiz.dataset.urlResultados;   // contiene /0/ como marcador
  var URL_VOTACION = raiz.dataset.urlVotacion;
  var REFRESCO_MS = 15000;

  var elKpis = document.getElementById("panel-kpis");
  var elParticipacion = document.getElementById("panel-participacion");
  var elSelector = document.getElementById("panel-selector");
  var elResultados = document.getElementById("panel-resultados");
  var elError = document.getElementById("panel-error");
  var elActualizado = document.getElementById("panel-actualizado");

  function crear(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto !== undefined) el.textContent = texto;
    return el;
  }

  function vaciar(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function urlConId(plantilla, id) {
    return plantilla.replace("/0/", "/" + id + "/");
  }

  function pedir(url) {
    return fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" }).then(function (r) {
      return r.json().then(function (datos) {
        if (!r.ok) {
          var e = new Error(datos.error || "Error " + r.status);
          e.estado = r.status;
          throw e;
        }
        return datos;
      });
    });
  }

  function mostrarError(msg) {
    elError.textContent = msg;
    elError.classList.remove("d-none");
  }

  function ocultarError() {
    elError.classList.add("d-none");
  }

  function pintarKpis(totales, porEstado) {
    vaciar(elKpis);
    var items = [
      ["Ediciones", totales.ediciones],
      ["Categorías", totales.categorias],
      ["Votaciones", totales.votaciones],
      ["Opciones", totales.opciones],
      ["Votos emitidos", totales.votos],
    ];
    items.forEach(function (it) {
      var col = crear("div", "col");
      var caja = crear("div", "kpi p-3 h-100");
      caja.appendChild(crear("div", "cifra", String(it[1])));
      caja.appendChild(crear("div", "small text-muted", it[0]));
      col.appendChild(caja);
      elKpis.appendChild(col);
    });
    document.getElementById("panel-estados").textContent =
      "Abiertas: " + (porEstado["Abierta"] || 0) +
      " · Próximas: " + (porEstado["Próxima"] || 0) +
      " · Cerradas: " + (porEstado["Cerrada"] || 0);
  }

  function pintarParticipacion(votaciones) {
    vaciar(elParticipacion);
    if (!votaciones.length) {
      elParticipacion.appendChild(crear("p", "text-muted", "Aún no hay votaciones publicadas."));
      return;
    }
    var max = Math.max.apply(null, votaciones.map(function (v) { return v.total_votos; })) || 1;
    votaciones.forEach(function (v) {
      var fila = crear("div", "mb-3");
      var cab = crear("div", "d-flex justify-content-between small");
      var enlace = crear("a", "text-decoration-none text-festival fw-semibold", v.titulo);
      enlace.href = urlConId(URL_VOTACION, v.id);
      cab.appendChild(enlace);
      cab.appendChild(crear("span", "text-muted", v.total_votos + " voto(s) · " + v.estado));
      var pista = crear("div", "barra mt-1");
      var relleno = crear("span");
      relleno.style.width = Math.round((v.total_votos * 100) / max) + "%";
      pista.appendChild(relleno);
      fila.appendChild(cab);
      fila.appendChild(pista);
      elParticipacion.appendChild(fila);
    });
  }

  function llenarSelector(votaciones) {
    var actual = elSelector.value;
    vaciar(elSelector);
    if (!votaciones.length) {
      var vacio = crear("option", "", "No hay votaciones");
      vacio.value = "";
      elSelector.appendChild(vacio);
      return;
    }
    votaciones.forEach(function (v) {
      var texto = v.titulo + " (" + v.estado + ")" + (v.resultados_disponibles ? "" : " · resultados al cierre");
      var op = crear("option", "", texto);
      op.value = String(v.id);
      op.dataset.disponible = v.resultados_disponibles ? "1" : "0";
      elSelector.appendChild(op);
    });
    if (actual && elSelector.querySelector('option[value="' + actual + '"]')) {
      elSelector.value = actual;                       // conserva la elección del usuario
    } else {
      var primera = votaciones.filter(function (v) { return v.resultados_disponibles; })[0];
      if (primera) elSelector.value = String(primera.id);  // por defecto, una con resultados
    }
  }

  function pintarResultados(datos) {
    vaciar(elResultados);
    var cab = crear("p", "small text-muted",
      datos.total_votos + " voto(s) en total" + (datos.parcial ? " · resultado parcial (solo personal)" : ""));
    elResultados.appendChild(cab);
    if (!datos.resultados.length) {
      elResultados.appendChild(crear("p", "text-muted", "Esta votación no tiene opciones."));
      return;
    }
    datos.resultados.forEach(function (r) {
      var fila = crear("div", "mb-3");
      var linea = crear("div", "d-flex justify-content-between small");
      linea.appendChild(crear("span", "fw-semibold", r.nombre + (r.lider ? " ★" : "")));
      linea.appendChild(crear("span", "text-muted", r.votos + " · " + r.porcentaje.toFixed(1) + "%"));
      var pista = crear("div", "barra mt-1" + (r.lider ? " ganadora" : ""));
      var relleno = crear("span");
      relleno.style.width = r.porcentaje + "%";
      pista.appendChild(relleno);
      fila.appendChild(linea);
      fila.appendChild(pista);
      elResultados.appendChild(fila);
    });
  }

  function cargarResultados() {
    var id = elSelector.value;
    if (!id) {
      vaciar(elResultados);
      return Promise.resolve();
    }
    return pedir(urlConId(URL_RESULTADOS, id))
      .then(pintarResultados)
      .catch(function (e) {
        vaciar(elResultados);
        var tipo = e.estado === 403 ? "text-muted" : "text-danger";
        elResultados.appendChild(crear("p", tipo, e.message));
      });
  }

  function cargar() {
    return pedir(URL_RESUMEN)
      .then(function (datos) {
        ocultarError();
        pintarKpis(datos.totales, datos.votaciones_por_estado);
        pintarParticipacion(datos.votaciones);
        llenarSelector(datos.votaciones);
        elActualizado.textContent = "Actualizado " + new Date().toLocaleTimeString("es-CO");
        return cargarResultados();
      })
      .catch(function (e) {
        mostrarError("No se pudieron cargar los datos: " + e.message);
      });
  }

  elSelector.addEventListener("change", cargarResultados);
  cargar();
  setInterval(cargar, REFRESCO_MS);
})();
