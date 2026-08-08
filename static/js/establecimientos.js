(function () {
  'use strict';

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

  function enviarForm(url, formData) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: formData,
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const menu = document.getElementById('menu-establecimientos');
    if (!menu) return;

    menu.addEventListener('click', function (event) {
      const boton = event.target.closest('[data-establecimiento-id]');
      if (!boton) return;
      const formData = new FormData();
      formData.append('establecimiento_id', boton.getAttribute('data-establecimiento-id') || '');
      enviarForm('/api/establecimientos/seleccionar/', formData).then(function (response) {
        if (response.ok) {
          window.location.reload();
        }
      });
    });
  });

  document.addEventListener('DOMContentLoaded', function () {
    const formulario = document.getElementById('form-nuevo-establecimiento');
    if (!formulario) return;

    formulario.addEventListener('submit', function (event) {
      event.preventDefault();
      const boton = document.getElementById('btn-guardar-establecimiento');
      const errorBox = document.getElementById('establecimiento-error');
      if (errorBox) errorBox.classList.add('d-none');

      if (!formulario.reportValidity()) return;

      boton.disabled = true;
      enviarForm('/api/establecimientos/crear/', new FormData(formulario))
        .then(function (response) {
          return response.json().then(function (data) {
            if (!response.ok) {
              if (errorBox) {
                errorBox.textContent = data.error || 'No se pudo registrar el establecimiento.';
                errorBox.classList.remove('d-none');
              }
              return;
            }
            window.location.reload();
          });
        })
        .finally(function () {
          boton.disabled = false;
        });
    });
  });
})();
