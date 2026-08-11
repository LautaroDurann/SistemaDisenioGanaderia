(function () {
  'use strict';

  const INTERVALO_REFRESCO = 60000;

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function escapeHTML(valor) {
    return String(valor ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function actualizarBadge(noLeidas) {
    const badge = document.getElementById('notificaciones-badge');
    if (!badge) return;
    badge.textContent = noLeidas;
    badge.classList.toggle('d-none', !Number(noLeidas));
  }

  function renderMenu(notificaciones) {
    const menu = document.getElementById('notificaciones-menu');
    if (!menu) return;

    menu.innerHTML = '';
    if (!notificaciones.length) {
      const vacio = document.createElement('span');
      vacio.className = 'dropdown-item-text text-secondary small';
      vacio.textContent = 'Sin notificaciones.';
      menu.appendChild(vacio);
      return;
    }

    notificaciones.forEach((notificacion, indice) => {
      const enlace = document.createElement('a');
      enlace.className = 'dropdown-item';
      enlace.href = notificacion.url || '/';
      enlace.dataset.id = notificacion.id;
      enlace.dataset.leida = notificacion.leida ? '1' : '0';
      enlace.title = notificacion.detalle || notificacion.titulo;
      enlace.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <div class="vacapp-alert-icon ${escapeHTML(notificacion.color)}"><i class="bi ${escapeHTML(notificacion.icono)}"></i></div>
          <div class="flex-grow-1">
            <div class="fw-semibold text-truncate">${escapeHTML(notificacion.titulo)}</div>
            <small class="text-secondary text-truncate d-block" style="max-width: 18rem;">${escapeHTML(notificacion.detalle)}</small>
          </div>
          ${notificacion.leida ? '' : '<span class="badge text-bg-warning notif-punto" title="Sin leer">&nbsp;</span>'}
        </div>`;
      menu.appendChild(enlace);
      if (indice < notificaciones.length - 1) {
        const separador = document.createElement('div');
        separador.className = 'dropdown-divider my-1';
        menu.appendChild(separador);
      }
    });
  }

  function renderModal(notificaciones) {
    const lista = document.getElementById('notificaciones-lista');
    if (!lista) return;

    const resumen = document.getElementById('notificaciones-resumen');
    const noLeidas = notificaciones.filter((n) => !n.leida).length;
    if (resumen) {
      resumen.textContent = noLeidas
        ? `${noLeidas} sin leer de ${notificaciones.length}`
        : `${notificaciones.length} notificaciones`;
    }

    lista.innerHTML = '';
    if (!notificaciones.length) {
      lista.innerHTML = '<div class="text-secondary small">No hay notificaciones.</div>';
      return;
    }

    notificaciones.forEach((notificacion) => {
      const fila = document.createElement('div');
      fila.className = 'd-flex align-items-center gap-3 p-2 rounded notif-fila' +
        (notificacion.leida ? ' notif-leida' : ' notif-no-leida');
      fila.innerHTML = `
        <div class="vacapp-alert-icon ${escapeHTML(notificacion.color)}"><i class="bi ${escapeHTML(notificacion.icono)}"></i></div>
        <div class="flex-grow-1">
          <div class="fw-semibold">${escapeHTML(notificacion.titulo)}</div>
          <small class="text-secondary d-block">${escapeHTML(notificacion.detalle)}</small>
          <small class="text-secondary d-block">${escapeHTML(notificacion.creada)}</small>
        </div>
        <div class="d-flex flex-shrink-0 gap-1">
          <a href="${escapeHTML(notificacion.url || '/')}" class="btn btn-sm btn-outline-primary" title="Ir al módulo" data-accion="ir" data-id="${notificacion.id}">
            <i class="bi bi-box-arrow-up-right"></i>
          </a>
          <button type="button" class="btn btn-sm btn-outline-success ${notificacion.leida ? 'd-none' : ''}" title="Marcar como leída" data-accion="leer" data-id="${notificacion.id}">
            <i class="bi bi-check2"></i>
          </button>
          <button type="button" class="btn btn-sm btn-outline-danger" title="Eliminar" data-accion="eliminar" data-id="${notificacion.id}">
            <i class="bi bi-trash"></i>
          </button>
        </div>`;
      lista.appendChild(fila);
    });
  }

  function marcarLeida(id) {
    return fetch(`/api/notificaciones/${id}/leer/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    }).then((respuesta) => {
      if (!respuesta.ok) throw new Error();
    });
  }

  function eliminarNotificacion(id) {
    return fetch(`/api/notificaciones/${id}/eliminar/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    }).then((respuesta) => {
      if (!respuesta.ok) throw new Error();
    });
  }

  function marcarTodasLeidas() {
    return fetch('/api/notificaciones/leer-todas/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    }).then((respuesta) => {
      if (!respuesta.ok) throw new Error();
    });
  }

  function eliminarTodas() {
    return fetch('/api/notificaciones/eliminar-todas/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    }).then((respuesta) => {
      if (!respuesta.ok) throw new Error();
    });
  }

  async function actualizarTodo() {
    try {
      const respuesta = await fetch('/api/notificaciones/', { method: 'GET' });
      if (!respuesta.ok) throw new Error();
      const cuerpo = await respuesta.json();
      actualizarBadge(cuerpo.no_leidas);
      renderMenu(cuerpo.notificaciones);
      renderModal(cuerpo.notificaciones);
    } catch {
      actualizarBadge(0);
    }
  }

  function abrirModalSiCorresponde() {
    if (window.location.hash !== '#notificaciones') return;
    const modalEl = document.getElementById('modal-notificaciones');
    if (modalEl && window.bootstrap) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const menu = document.getElementById('notificaciones-menu');
    if (!menu) return;

    actualizarTodo();
    setInterval(actualizarTodo, INTERVALO_REFRESCO);
    abrirModalSiCorresponde();

    const toggle = document.getElementById('notificaciones-toggle');
    if (toggle) {
      toggle.addEventListener('show.bs.dropdown', actualizarTodo);
    }

    // Clic en una notificación del menú: se marca como leída y navega al módulo.
    menu.addEventListener('click', function (event) {
      const enlace = event.target.closest('a.dropdown-item');
      if (!enlace || !enlace.dataset.id || enlace.dataset.leida === '1') return;
      event.preventDefault();
      const destino = enlace.href;
      marcarLeida(enlace.dataset.id).finally(() => {
        window.location.href = destino;
      });
    });

    // Acciones dentro del modal "Ver todas".
    const lista = document.getElementById('notificaciones-lista');
    if (lista) {
      lista.addEventListener('click', function (event) {
        const boton = event.target.closest('[data-accion]');
        if (!boton) return;
        const accion = boton.dataset.accion;
        const id = boton.dataset.id;
        if (accion === 'leer') {
          marcarLeida(id).then(actualizarTodo);
        } else if (accion === 'eliminar') {
          eliminarNotificacion(id).then(actualizarTodo);
        } else if (accion === 'ir') {
          event.preventDefault();
          const destino = boton.href;
          marcarLeida(id).finally(() => {
            window.location.href = destino;
          });
        }
      });
    }

    const btnLeerTodas = document.getElementById('btn-notificaciones-leer-todas');
    if (btnLeerTodas) {
      btnLeerTodas.addEventListener('click', () => marcarTodasLeidas().then(actualizarTodo));
    }

    const btnEliminarTodas = document.getElementById('btn-notificaciones-eliminar-todas');
    if (btnEliminarTodas) {
      btnEliminarTodas.addEventListener('click', () => {
        if (window.confirm('¿Eliminar todas las notificaciones?')) {
          eliminarTodas().then(actualizarTodo);
        }
      });
    }
  });
})();
