(() => {
  const $ = (id) => document.getElementById(id);
  const getCookie = (name) => document.cookie.split('; ').find((row) => row.startsWith(name + '='))?.split('=')[1] || '';

  let confirmarCallback = null;

  function confirmarAccion(titulo, mensaje, onConfirm) {
    const tituloEl = $('confirmar-titulo');
    const mensajeEl = $('confirmar-mensaje');
    if (tituloEl) tituloEl.textContent = titulo;
    if (mensajeEl) mensajeEl.textContent = mensaje;
    confirmarCallback = onConfirm;
    const modalEl = $('modalConfirmar');
    if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    } else if (window.confirm(mensaje)) {
      onConfirm();
    }
  }

  function mostrarError(mensaje) {
    const feedback = $('est-guardar-error');
    if (!feedback) return;
    feedback.textContent = mensaje;
    feedback.style.display = 'block';
  }

  function mostrarExito(btn, texto) {
    if (!btn) return;
    const original = btn.innerHTML;
    btn.innerHTML = `<i class="bi bi-check-lg me-1"></i> ${texto}`;
    setTimeout(() => (btn.innerHTML = original), 1800);
  }

  // Eliminación del establecimiento activo (solo propietario).
  document.addEventListener('click', (event) => {
    const boton = event.target.closest('#btn-eliminar-establecimiento');
    if (!boton) return;
    const id = boton.dataset.establecimientoId;
    const nombre = boton.dataset.establecimientoNombre;
    confirmarAccion(
      'Dar de baja establecimiento',
      `¿Deseas dar de baja "${nombre}"? Dejará de estar disponible y no se mostrarán sus registros.`,
      async () => {
        mostrarError('');
        try {
          const r = await fetch(`/api/establecimientos/${id}/eliminar/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.error || 'No se pudo eliminar el establecimiento.');
          window.location.href = '/';
        } catch (err) {
          mostrarError(err.message);
        }
      }
    );
  });

  document.addEventListener('DOMContentLoaded', () => {
    const btnAceptar = $('confirmar-btn-aceptar');
    if (btnAceptar) {
      btnAceptar.addEventListener('click', () => {
        if (typeof confirmarCallback === 'function') confirmarCallback();
        bootstrap.Modal.getOrCreateInstance($('modalConfirmar')).hide();
      });
    }

    // Vista previa del logo antes de guardar
    const logoInput = $('est-logo-input');
    if (logoInput) {
      logoInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
          $('est-logo-preview').innerHTML = `<img src="${ev.target.result}" alt="Logo del establecimiento" />`;
        };
        reader.readAsDataURL(file);
      });
    }

    // Eliminación del logo del establecimiento activo
    const btnEliminarLogo = $('est-logo-eliminar-btn');
    if (btnEliminarLogo) {
      btnEliminarLogo.addEventListener('click', () => {
        confirmarAccion(
          'Eliminar logo',
          '¿Deseas eliminar el logo del establecimiento? Esta acción no se puede deshacer.',
          async () => {
            mostrarError('');
            try {
              const r = await fetch('/api/establecimientos/config/logo/eliminar/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
              });
              const data = await r.json();
              if (!r.ok) throw new Error(data.error || 'No se pudo eliminar el logo.');
              $('est-logo-preview').innerHTML = '<i class="bi bi-image"></i>';
              $('est-logo-input').value = '';
              $('est-logo-eliminar-btn').classList.add('d-none');
            } catch (err) {
              mostrarError(err.message);
            }
          }
        );
      });
    }

    // Guardado de los datos del establecimiento activo (nombre, ubicación y logo)
    const form = $('form-establecimiento');
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        mostrarError('');
        const btn = $('est-guardar-btn');
        const formData = new FormData();
        formData.append('nombre', $('est-nombre').value.trim());
        formData.append('fecha_inicio', $('est-fecha-inicio').value);
        formData.append('ubicacion', $('est-ubicacion').value.trim());
        const logoFile = $('est-logo-input').files[0];
        if (logoFile) formData.append('logo', logoFile);
        try {
          const r = await fetch('/api/establecimientos/config/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            body: formData,
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.error || 'No se pudo guardar la configuración.');
          mostrarExito(btn, 'Cambios guardados');
          $('est-logo-input').value = '';
          if (data.establecimiento?.logo) {
            $('est-logo-preview').innerHTML =
              `<img src="${data.establecimiento.logo}" alt="Logo del establecimiento" />`;
          }
        } catch (err) {
          mostrarError(err.message);
        }
      });
    }
  });
})();
