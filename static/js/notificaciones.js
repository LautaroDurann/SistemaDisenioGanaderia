(function () {
  'use strict';

  const INTERVALO_REFRESCO = 60000;

  function escapeHTML(valor) {
    return String(valor ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderNotificaciones(notificaciones) {
    const menu = document.getElementById('notificaciones-menu');
    const badge = document.getElementById('notificaciones-badge');
    if (!menu) return;

    const lista = Array.isArray(notificaciones) ? notificaciones : [];
    menu.innerHTML = '';

    if (!lista.length) {
      const vacio = document.createElement('span');
      vacio.className = 'dropdown-item-text text-secondary small';
      vacio.textContent = 'Sin notificaciones.';
      menu.appendChild(vacio);
    } else {
      lista.forEach((notificacion, indice) => {
        const item = document.createElement('a');
        item.className = 'dropdown-item';
        item.href = '/';
        item.title = notificacion.detalle || notificacion.titulo;
        item.innerHTML = `
          <div class="d-flex align-items-center gap-2">
            <div class="vacapp-alert-icon ${escapeHTML(notificacion.color)}"><i class="bi ${escapeHTML(notificacion.icono)}"></i></div>
            <div>
              <div class="fw-semibold text-truncate">${escapeHTML(notificacion.titulo)}</div>
              <small class="text-secondary text-truncate d-block" style="max-width: 20rem;">${escapeHTML(notificacion.detalle)}</small>
            </div>
          </div>`;
        menu.appendChild(item);
        if (indice < lista.length - 1) {
          const separador = document.createElement('div');
          separador.className = 'dropdown-divider my-1';
          menu.appendChild(separador);
        }
      });
    }

    if (badge) {
      badge.textContent = lista.length;
      badge.classList.toggle('d-none', lista.length === 0);
    }
  }

  async function cargarNotificaciones() {
    const menu = document.getElementById('notificaciones-menu');
    if (!menu) return;
    try {
      const respuesta = await fetch('/api/notificaciones/', { method: 'GET' });
      if (!respuesta.ok) throw new Error();
      const cuerpo = await respuesta.json();
      renderNotificaciones(cuerpo.notificaciones);
    } catch {
      const badge = document.getElementById('notificaciones-badge');
      if (badge) badge.classList.add('d-none');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const menu = document.getElementById('notificaciones-menu');
    if (!menu) return;

    cargarNotificaciones();
    setInterval(cargarNotificaciones, INTERVALO_REFRESCO);

    const toggle = document.getElementById('notificaciones-toggle');
    if (toggle) {
      toggle.addEventListener('show.bs.dropdown', cargarNotificaciones);
    }
  });
})();
