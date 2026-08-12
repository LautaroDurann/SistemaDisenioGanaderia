      const SELECTOR_SIDEBAR_WRAPPER = '.sidebar-wrapper';
      const Default = {
        scrollbarTheme: 'os-theme-light',
        scrollbarAutoHide: 'leave',
        scrollbarClickScroll: true,
      };
      document.addEventListener('DOMContentLoaded', function () {
        const sidebarWrapper = document.querySelector(SELECTOR_SIDEBAR_WRAPPER);
        const isMobile = window.innerWidth <= 992;
        if (sidebarWrapper && OverlayScrollbarsGlobal?.OverlayScrollbars !== undefined && !isMobile) {
          OverlayScrollbarsGlobal.OverlayScrollbars(sidebarWrapper, {
            scrollbars: {
              theme: Default.scrollbarTheme,
              autoHide: Default.scrollbarAutoHide,
              clickScroll: Default.scrollbarClickScroll,
            },
          });
        }
      });

      // ------------------------------------------------------------------
      // Modal de confirmacion generico (para toda accion critica/destructiva)
      // ------------------------------------------------------------------
      let confirmarCallback = null;

      function confirmarAccion(titulo, mensaje, onConfirm) {
        const modalEl = document.getElementById('modalConfirmar');
        const tituloEl = document.getElementById('confirmar-titulo');
        const mensajeEl = document.getElementById('confirmar-mensaje');
        if (tituloEl) tituloEl.textContent = titulo;
        if (mensajeEl) mensajeEl.textContent = mensaje;
        confirmarCallback = onConfirm;
        if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          bootstrap.Modal.getOrCreateInstance(modalEl).show();
        } else if (window.confirm(mensaje)) {
          onConfirm();
        }
      }

      // Eliminación del establecimiento activo (solo propietario).
      // Registrado por delegación para que funcione aunque otros componentes
      // de la página fallen al inicializar o haya una versión del JS en caché.
      document.addEventListener('click', (event) => {
        const boton = event.target.closest('#btn-eliminar-establecimiento');
        if (!boton) return;
        const id = boton.dataset.establecimientoId;
        const nombre = boton.dataset.establecimientoNombre;
        confirmarAccion(
          'Dar de baja establecimiento',
          `¿Deseas dar de baja "${nombre}"? Dejará de estar disponible y no se mostrarán sus registros.`,
          async () => {
            mostrarErrorEstablecimiento('');
            try {
              const r = await fetch(`/api/establecimientos/${id}/eliminar/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
              });
              const data = await r.json();
              if (!r.ok) throw new Error(data.error || 'No se pudo eliminar el establecimiento.');
              window.location.href = '/';
            } catch (err) {
              mostrarErrorEstablecimiento(err.message);
            }
          }
        );
      });

      // ------------------------------------------------------------------
      // Feedback visual reutilizable en botones (guardado / accion ok)
      // ------------------------------------------------------------------
      function mostrarExito(botonId, texto) {
        const btn = typeof botonId === 'string' ? document.getElementById(botonId) : botonId;
        if (!btn) return;
        const original = btn.innerHTML;
        btn.innerHTML = `<i class="bi bi-check-lg me-1"></i> ${texto}`;
        setTimeout(() => (btn.innerHTML = original), 1800);
      }

      // ------------------------------------------------------------------
      // Copia de seguridad
      // ------------------------------------------------------------------
      function getCookie(nombre) {
        return document.cookie.split('; ').find((row) => row.startsWith(nombre + '='))?.split('=')[1] || '';
      }

      function mostrarErrorDb(mensaje) {
        const feedback = document.getElementById('db-error');
        if (!feedback) return;
        feedback.textContent = mensaje;
        feedback.style.display = 'block';
      }

      function ocultarErrorDb() {
        const feedback = document.getElementById('db-error');
        if (feedback) feedback.style.display = 'none';
      }

      function agregarFilaRespaldo(respaldo) {
        const vacia = document.getElementById('fila-respaldos-vacia');
        if (vacia) vacia.remove();
        const tbody = document.getElementById('tabla-respaldos');
        if (!tbody) return;
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="font-monospace small">${respaldo.nombre}</td>
          <td class="small">${respaldo.fecha}</td>
          <td class="small">${respaldo.tamano}</td>
          <td class="text-end">
            <button type="button" class="btn btn-sm btn-outline-warning" data-accion="restaurar" data-respaldo="${respaldo.nombre}">
              <i class="bi bi-arrow-counterclockwise me-1"></i> Restaurar
            </button>
            <button type="button" class="btn btn-sm btn-outline-danger" data-accion="eliminar" data-respaldo="${respaldo.nombre}">
              <i class="bi bi-trash me-1"></i> Eliminar
            </button>
          </td>`;
        tbody.appendChild(tr);
      }

      function mostrarFilaVacia() {
        const tbody = document.getElementById('tabla-respaldos');
        if (!tbody || tbody.querySelector('tr:not(#fila-respaldos-vacia)')) return;
        const tr = document.createElement('tr');
        tr.id = 'fila-respaldos-vacia';
        tr.innerHTML = '<td colspan="4" class="text-secondary small text-center py-3">Todavía no se generó ningún respaldo. Usá "Crear respaldo" para guardar una copia de seguridad de la base de datos.</td>';
        tbody.appendChild(tr);
      }

      async function crearRespaldo(boton) {
        ocultarErrorDb();
        boton.disabled = true;
        try {
          const r = await fetch('/api/configuracion/respaldos/crear/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.error || 'No se pudo crear el respaldo.');
          agregarFilaRespaldo(data.respaldo);
          document.getElementById('db-ultimo-respaldo').textContent = data.respaldo.fecha;
          mostrarExito(boton, 'Respaldo creado');
        } catch (err) {
          mostrarErrorDb(err.message);
        } finally {
          boton.disabled = false;
        }
      }

      async function restaurarRespaldo(nombre) {
        ocultarErrorDb();
        try {
          const r = await fetch('/api/configuracion/respaldos/restaurar/', {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ respaldo: nombre }),
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.error || 'No se pudo restaurar el respaldo.');
          // Los datos cambiaron: se recarga la página para reflejar el estado restaurado.
          window.location.reload();
        } catch (err) {
          mostrarErrorDb(err.message);
        }
      }

      async function eliminarRespaldo(nombre, boton) {
        ocultarErrorDb();
        boton.disabled = true;
        try {
          const r = await fetch('/api/configuracion/respaldos/eliminar/', {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ respaldo: nombre }),
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.error || 'No se pudo eliminar el respaldo.');
          boton.closest('tr').remove();
          mostrarFilaVacia();
          const filas = document.querySelectorAll('#tabla-respaldos tr:not(#fila-respaldos-vacia)');
          if (filas.length) {
            document.getElementById('db-ultimo-respaldo').textContent = filas[0].querySelector('td:nth-child(2)').textContent.trim();
          } else {
            document.getElementById('db-ultimo-respaldo').textContent = 'Sin respaldos';
          }
        } catch (err) {
          mostrarErrorDb(err.message);
        } finally {
          boton.disabled = false;
        }
      }

      async function optimizarBaseDeDatos(boton) {
        ocultarErrorDb();
        boton.disabled = true;
        try {
          const r = await fetch('/api/configuracion/base-de-datos/optimizar/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.error || 'No se pudo optimizar la base de datos.');
          mostrarExito(boton, 'Base optimizada');
        } catch (err) {
          mostrarErrorDb(err.message);
        } finally {
          boton.disabled = false;
        }
      }

      // Acciones de respaldo registradas por delegación para que también
      // funcionen sobre las filas agregadas dinámicamente tras crear un respaldo.
      document.addEventListener('click', (event) => {
        const botonRestaurar = event.target.closest('[data-accion="restaurar"]');
        if (botonRestaurar) {
          confirmarAccion(
            'Restaurar respaldo',
            `Esto reemplazará los datos actuales por los del respaldo "${botonRestaurar.dataset.respaldo}". Esta acción no se puede deshacer. ¿Deseas continuar?`,
            () => restaurarRespaldo(botonRestaurar.dataset.respaldo)
          );
          return;
        }
        const botonEliminar = event.target.closest('[data-accion="eliminar"]');
        if (botonEliminar) {
          confirmarAccion(
            'Eliminar respaldo',
            `¿Deseas eliminar el respaldo "${botonEliminar.dataset.respaldo}"? Esta acción no se puede deshacer.`,
            () => eliminarRespaldo(botonEliminar.dataset.respaldo, botonEliminar)
          );
        }
      });

      // ------------------------------------------------------------------
      // Establecimiento
      // ------------------------------------------------------------------
      function mostrarErrorEstablecimiento(mensaje) {
        const feedback = document.getElementById('est-guardar-error');
        feedback.textContent = mensaje;
        feedback.style.display = 'block';
      }

      document.addEventListener('DOMContentLoaded', () => {
        // Conserva la pestaña activa de configuración entre recargas (útil al restaurar un respaldo).
        const navLinks = document.querySelectorAll('.vacapp-config-nav .nav-link');
        const tabGuardada = sessionStorage.getItem('config-tab');
        if (tabGuardada && typeof bootstrap !== 'undefined') {
          const enlace = document.querySelector(`.vacapp-config-nav .nav-link[data-bs-target="${tabGuardada}"]`);
          if (enlace) bootstrap.Tab.getOrCreateInstance(enlace).show();
        }
        navLinks.forEach((enlace) => {
          enlace.addEventListener('shown.bs.tab', () => {
            sessionStorage.setItem('config-tab', enlace.getAttribute('data-bs-target'));
          });
        });

        document.getElementById('confirmar-btn-aceptar').addEventListener('click', () => {
          if (typeof confirmarCallback === 'function') confirmarCallback();
          bootstrap.Modal.getOrCreateInstance(document.getElementById('modalConfirmar')).hide();
        });

        // Vista previa del logo antes de guardar
        document.getElementById('est-logo-input').addEventListener('change', (e) => {
          const file = e.target.files[0];
          if (!file) return;
          const reader = new FileReader();
          reader.onload = (ev) => {
            document.getElementById('est-logo-preview').innerHTML = `<img src="${ev.target.result}" alt="Logo del establecimiento" />`;
          };
          reader.readAsDataURL(file);
        });

        // Eliminación del logo del establecimiento activo
        document.getElementById('est-logo-eliminar-btn')?.addEventListener('click', () => {
          confirmarAccion(
            'Eliminar logo',
            '¿Deseas eliminar el logo del establecimiento? Esta acción no se puede deshacer.',
            async () => {
              mostrarErrorEstablecimiento('');
              try {
                const r = await fetch('/api/establecimientos/config/logo/eliminar/', {
                  method: 'POST',
                  headers: { 'X-CSRFToken': getCookie('csrftoken') },
                });
                const data = await r.json();
                if (!r.ok) throw new Error(data.error || 'No se pudo eliminar el logo.');
                document.getElementById('est-logo-preview').innerHTML = '<i class="bi bi-image"></i>';
                document.getElementById('est-logo-input').value = '';
                document.getElementById('est-logo-eliminar-btn').classList.add('d-none');
              } catch (err) {
                mostrarErrorEstablecimiento(err.message);
              }
            }
          );
        });

        // Guardado de los datos del establecimiento activo (nombre, ubicacion y logo)
        document.getElementById('form-establecimiento').addEventListener('submit', async (e) => {
          e.preventDefault();
          mostrarErrorEstablecimiento('');
          const btn = document.getElementById('est-guardar-btn');
          const formData = new FormData();
          formData.append('nombre', document.getElementById('est-nombre').value.trim());
          formData.append('fecha_inicio', document.getElementById('est-fecha-inicio').value);
          formData.append('ubicacion', document.getElementById('est-ubicacion').value.trim());
          const logoFile = document.getElementById('est-logo-input').files[0];
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
            document.getElementById('est-logo-input').value = '';
            if (data.establecimiento?.logo) {
              document.getElementById('est-logo-preview').innerHTML =
                `<img src="${data.establecimiento.logo}" alt="Logo del establecimiento" />`;
            }
          } catch (err) {
            mostrarErrorEstablecimiento(err.message);
          }
        });

        // Copia de seguridad: crear respaldo
        document.getElementById('btn-crear-respaldo').addEventListener('click', function () {
          crearRespaldo(this);
        });

        // Copia de seguridad: optimizar base de datos
        document.getElementById('btn-optimizar-db').addEventListener('click', function () {
          confirmarAccion(
            'Optimizar base de datos',
            'La base de datos puede quedar unos instantes sin responder mientras se optimiza. ¿Deseas continuar?',
            () => optimizarBaseDeDatos(this)
          );
        });
      });
    