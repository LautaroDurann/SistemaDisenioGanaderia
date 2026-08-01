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
    

      (() => {
        'use strict';
        const STORAGE_KEY = 'lte-theme';
        const getStoredTheme = () => localStorage.getItem(STORAGE_KEY);
        const setStoredTheme = (theme) => localStorage.setItem(STORAGE_KEY, theme);
        const prefersDark = () => globalThis.matchMedia('(prefers-color-scheme: dark)').matches;
        const getPreferredTheme = () => {
          const stored = getStoredTheme();
          if (stored) return stored;
          return prefersDark() ? 'dark' : 'light';
        };
        const setTheme = (theme) => {
          const resolved = theme === 'auto' ? (prefersDark() ? 'dark' : 'light') : theme;
          document.documentElement.setAttribute('data-bs-theme', resolved);
        };
        setTheme(getPreferredTheme());
        const showActiveTheme = (theme) => {
          document.querySelectorAll('[data-bs-theme-value]').forEach((el) => {
            el.classList.remove('active');
            el.setAttribute('aria-pressed', 'false');
            const check = el.querySelector('.bi-check-lg');
            if (check) check.classList.add('d-none');
          });
          const active = document.querySelector(`[data-bs-theme-value="${theme}"]`);
          if (active) {
            active.classList.add('active');
            active.setAttribute('aria-pressed', 'true');
            const check = active.querySelector('.bi-check-lg');
            if (check) check.classList.remove('d-none');
          }
          document.querySelectorAll('[data-lte-theme-icon]').forEach((icon) => {
            icon.classList.toggle('d-none', icon.dataset.lteThemeIcon !== theme);
          });
        };
        globalThis.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
          const stored = getStoredTheme();
          if (!stored || stored === 'auto') setTheme(getPreferredTheme());
        });
        document.addEventListener('DOMContentLoaded', () => {
          showActiveTheme(getPreferredTheme());
          document.querySelectorAll('[data-bs-theme-value]').forEach((toggle) => {
            toggle.addEventListener('click', () => {
              const theme = toggle.getAttribute('data-bs-theme-value');
              setStoredTheme(theme);
              setTheme(theme);
              showActiveTheme(theme);
            });
          });
        });
      })();
    

      // ------------------------------------------------------------------
      // MOCK DATA: reemplazar por datos reales cuando se conecte con Django.
      // "Hoy" de referencia para calcular antiguedad/ultimo acceso: 2026-07-14.
      // ------------------------------------------------------------------
      const HOY = '2026-07-14';

      const COLOR_ROL = {
        Administrador: '#212529',
        Encargado: '#0d6efd',
        Veterinario: '#0dcaf0',
        Operario: '#6c757d',
      };

      const USUARIOS = window.GANASTOCK_DATA?.usuarios ?? [
        { id: 1, nombre: 'Juan', apellido: 'Fernandez', usuario: 'jfernandez', email: 'juan.fernandez@vacapp.com', telefono: '+54 9 3644 111111', cargo: 'Gerente general', rol: 'Administrador', estado: 'Activo', creado: '2023-02-10', acceso: '2026-07-14T08:30', conectado: true },
        { id: 2, nombre: 'Maria', apellido: 'Lopez', usuario: 'mlopez', email: 'maria.lopez@vacapp.com', telefono: '+54 9 3644 222222', cargo: 'Veterinaria de campo', rol: 'Veterinario', estado: 'Activo', creado: '2023-06-01', acceso: '2026-07-14T07:15', conectado: true },
        { id: 3, nombre: 'Carlos', apellido: 'Gomez', usuario: 'cgomez', email: 'carlos.gomez@vacapp.com', telefono: '+54 9 3644 333333', cargo: 'Encargado de establecimiento', rol: 'Encargado', estado: 'Activo', creado: '2024-01-15', acceso: '2026-07-13T18:40', conectado: false },
        { id: 4, nombre: 'Pedro', apellido: 'Ramirez', usuario: 'pramirez', email: 'pedro.ramirez@vacapp.com', telefono: '+54 9 3644 444444', cargo: 'Operario de campo', rol: 'Operario', estado: 'Activo', creado: '2024-03-22', acceso: '2026-07-10T09:05', conectado: false },
        { id: 5, nombre: 'Lucia', apellido: 'Fernandez', usuario: 'lfernandez', email: 'lucia.fernandez@vacapp.com', telefono: '+54 9 3644 555555', cargo: 'Veterinaria suplente', rol: 'Veterinario', estado: 'Inactivo', creado: '2024-05-05', acceso: '2026-05-20T12:00', conectado: false },
        { id: 6, nombre: 'Sofia', apellido: 'Torres', usuario: 'storres', email: 'sofia.torres@vacapp.com', telefono: '+54 9 3644 666666', cargo: 'Operaria de campo', rol: 'Operario', estado: 'Bloqueado', creado: '2024-08-18', acceso: '2026-06-02T16:20', conectado: false },
        { id: 7, nombre: 'Diego', apellido: 'Suarez', usuario: 'dsuarez', email: 'diego.suarez@vacapp.com', telefono: '+54 9 3644 777777', cargo: 'Encargado de potreros', rol: 'Encargado', estado: 'Activo', creado: '2025-01-09', acceso: '2026-07-12T10:50', conectado: false },
        { id: 8, nombre: 'Ana', apellido: 'Benitez', usuario: 'abenitez', email: 'ana.benitez@vacapp.com', telefono: '+54 9 3644 888888', cargo: 'Operaria de corrales', rol: 'Operario', estado: 'Activo', creado: '2025-04-30', acceso: '2026-07-14T06:45', conectado: true },
        { id: 9, nombre: 'Martin', apellido: 'Acosta', usuario: 'macosta', email: 'martin.acosta@vacapp.com', telefono: '+54 9 3644 999999', cargo: 'Administrador de sistemas', rol: 'Administrador', estado: 'Inactivo', creado: '2023-09-12', acceso: '2026-04-11T09:30', conectado: false },
        { id: 10, nombre: 'Rosa', apellido: 'Gimenez', usuario: 'rgimenez', email: 'rosa.gimenez@vacapp.com', telefono: '+54 9 3644 101010', cargo: 'Veterinaria de campo', rol: 'Veterinario', estado: 'Activo', creado: '2025-11-02', acceso: '2026-07-11T14:10', conectado: false },
      ];

      const ESTADO_BADGE = {
        Activo: 'text-bg-success',
        Inactivo: 'text-bg-secondary',
        Bloqueado: 'text-bg-danger',
      };

      const MODULOS = ['Dashboard', 'Stock', 'Movimientos', 'Potreros', 'Vacunacion', 'Pesajes', 'Alimentacion', 'Reportes', 'Usuarios', 'Configuracion'];
      const ROLES = ['Administrador', 'Encargado', 'Veterinario', 'Operario'];

      // Matriz de permisos por rol (mock, editable desde la UI pero no persistente).
      const PERMISOS = {
        Administrador: MODULOS.reduce((acc, m) => ({ ...acc, [m]: true }), {}),
        Encargado: { Dashboard: true, Stock: true, Movimientos: true, Potreros: true, Vacunacion: true, Pesajes: true, Alimentacion: true, Reportes: true, Usuarios: false, Configuracion: false },
        Veterinario: { Dashboard: true, Stock: false, Movimientos: false, Potreros: false, Vacunacion: true, Pesajes: true, Alimentacion: false, Reportes: true, Usuarios: false, Configuracion: false },
        Operario: { Dashboard: true, Stock: true, Movimientos: true, Potreros: true, Vacunacion: false, Pesajes: false, Alimentacion: true, Reportes: false, Usuarios: false, Configuracion: false },
      };

      const FILAS_POR_PAGINA = 6;
      let paginaActual = 1;
      let usuarioSeleccionado = USUARIOS[0].id;

      function nombreCompleto(u) {
        return `${u.nombre} ${u.apellido}`;
      }

      function iniciales(u) {
        return `${u.nombre[0]}${u.apellido[0]}`.toUpperCase();
      }

      function formatFecha(iso) {
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y}`;
      }

      function formatFechaHora(iso) {
        const [fecha, hora] = iso.split('T');
        return `${formatFecha(fecha)} ${hora}`;
      }

      function diasDesde(iso) {
        const soloFecha = iso.split('T')[0];
        return Math.round((new Date(`${HOY}T00:00:00`) - new Date(`${soloFecha}T00:00:00`)) / 86400000);
      }

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const rol = document.getElementById('f-rol').value;
        const estado = document.getElementById('f-estado').value;
        const ultimoAcceso = document.getElementById('f-ultimo-acceso').value;
        const antiguedad = document.getElementById('f-antiguedad').value;

        return USUARIOS.filter((u) => {
          if (buscar && !`${nombreCompleto(u)} ${u.email}`.toLowerCase().includes(buscar)) return false;
          if (rol && u.rol !== rol) return false;
          if (estado && u.estado !== estado) return false;

          if (ultimoAcceso) {
            const dias = diasDesde(u.acceso);
            if (ultimoAcceso === 'hoy' && dias > 0) return false;
            if (ultimoAcceso === 'semana' && dias > 7) return false;
            if (ultimoAcceso === 'mes' && dias > 30) return false;
            if (ultimoAcceso === 'viejo' && dias <= 30) return false;
          }

          if (antiguedad) {
            const dias = diasDesde(u.creado);
            if (antiguedad === 'nuevo' && dias > 30) return false;
            if (antiguedad === 'medio' && (dias <= 30 || dias > 182)) return false;
            if (antiguedad === 'viejo' && dias <= 182) return false;
          }

          return true;
        });
      }

      function renderTabla() {
        const filtrados = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(filtrados.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;
        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = filtrados.slice(inicio, inicio + FILAS_POR_PAGINA);

        document.getElementById('tabla-usuarios-body').innerHTML = pagina
          .map(
            (u) => `
          <tr>
            <td>
              <span class="vacapp-avatar-wrap">
                <span class="vacapp-avatar" style="background:${COLOR_ROL[u.rol]}">${iniciales(u)}</span>
                ${u.conectado ? '<span class="vacapp-online-dot" title="Conectado ahora"></span>' : ''}
              </span>
            </td>
            <td>
              <div class="fw-semibold">${nombreCompleto(u)}</div>
              <div class="small text-secondary">@${u.usuario}</div>
            </td>
            <td>${u.email}</td>
            <td>${u.rol}</td>
            <td><span class="badge ${ESTADO_BADGE[u.estado]}">${u.estado}</span></td>
            <td>${formatFechaHora(u.acceso)}</td>
            <td>${formatFecha(u.creado)}</td>
            <td class="text-end">
              <button type="button" class="btn btn-sm btn-outline-primary btn-ver-perfil" data-id="${u.id}" title="Ver perfil">
                <i class="bi bi-eye"></i>
              </button>
              <div class="dropdown d-inline-block">
                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                  <i class="bi bi-three-dots-vertical"></i>
                </button>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="#"><i class="bi bi-pencil-square me-2"></i>Editar</a></li>
                  <li><a class="dropdown-item" href="#"><i class="bi bi-key me-2"></i>Restablecer contrasena</a></li>
                  <li><a class="dropdown-item btn-roles-permisos" href="#"><i class="bi bi-shield-lock me-2"></i>Roles y permisos</a></li>
                  <li><a class="dropdown-item" href="#"><i class="bi bi-slash-circle me-2"></i>${u.estado === 'Activo' ? 'Desactivar' : 'Activar'}</a></li>
                  <li><hr class="dropdown-divider" /></li>
                  <li><a class="dropdown-item text-danger" href="#"><i class="bi bi-trash me-2"></i>Eliminar</a></li>
                </ul>
              </div>
            </td>
          </tr>`,
          )
          .join('');

        document.getElementById('tabla-resumen').textContent =
          filtrados.length === 0
            ? 'Sin resultados para los filtros aplicados.'
            : `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, filtrados.length)} de ${filtrados.length} usuarios.`;

        const paginacion = document.getElementById('tabla-paginacion');
        paginacion.innerHTML = '';
        for (let i = 1; i <= totalPaginas; i++) {
          const li = document.createElement('li');
          li.className = `page-item ${i === paginaActual ? 'active' : ''}`;
          li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
          li.addEventListener('click', (e) => {
            e.preventDefault();
            paginaActual = i;
            renderTabla();
          });
          paginacion.appendChild(li);
        }

        document.querySelectorAll('.btn-ver-perfil').forEach((btn) => {
          btn.addEventListener('click', () => {
            usuarioSeleccionado = Number(btn.dataset.id);
            renderPerfil();
            document.getElementById('perfil-usuario').scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
        });

        document.querySelectorAll('.btn-roles-permisos').forEach((btn) => {
          btn.addEventListener('click', (e) => {
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalRolesPermisos')).show();
          });
        });
      }

      function renderPerfil() {
        const u = USUARIOS.find((x) => x.id === usuarioSeleccionado);
        if (!u) return;

        const avatar = document.getElementById('perfil-avatar');
        avatar.textContent = iniciales(u);
        avatar.style.background = COLOR_ROL[u.rol];

        document.getElementById('perfil-nombre').textContent = nombreCompleto(u);
        document.getElementById('perfil-cargo').textContent = u.cargo;
        document.getElementById('perfil-email').textContent = u.email;
        document.getElementById('perfil-telefono').textContent = u.telefono;
        document.getElementById('perfil-rol').textContent = u.rol;
        document.getElementById('perfil-estado').innerHTML = `<span class="badge ${ESTADO_BADGE[u.estado]}">${u.estado}</span>`;
        document.getElementById('perfil-creacion').textContent = formatFecha(u.creado);
        document.getElementById('perfil-acceso').textContent = formatFechaHora(u.acceso);
      }

      function renderPermisos() {
        document.getElementById('permisos-thead-row').innerHTML =
          '<th>Modulo</th>' + ROLES.map((r) => `<th>${r}</th>`).join('');

        document.getElementById('permisos-tbody').innerHTML = MODULOS.map(
          (m) => `
          <tr>
            <td>${m}</td>
            ${ROLES.map(
              (r) => `
              <td>
                <div class="form-check form-switch d-inline-block">
                  <input class="form-check-input" type="checkbox" ${PERMISOS[r][m] ? 'checked' : ''} ${r === 'Administrador' ? 'disabled' : ''} data-rol="${r}" data-modulo="${m}" />
                </div>
              </td>`,
            ).join('')}
          </tr>`,
        ).join('');

        document.querySelectorAll('#permisos-tbody input[type="checkbox"]').forEach((chk) => {
          chk.addEventListener('change', () => {
            PERMISOS[chk.dataset.rol][chk.dataset.modulo] = chk.checked;
            if (usuarioSeleccionado && USUARIOS.find((u) => u.id === usuarioSeleccionado)?.rol === chk.dataset.rol) {
              renderPerfil();
            }
          });
        });
      }

      // ------------------------------------------------------------------
      // Hace que la fila "Tabla + Perfil del usuario" ocupe toda la altura
      // restante de la pantalla (entre el encabezado y el footer), en vez
      // de quedar con su alto natural de contenido.
      // ------------------------------------------------------------------
      function ajustarAlturaFilaCompleta() {
        const fila = document.getElementById('perfil-usuario');
        if (!fila) return;
        const footer = document.querySelector('.app-footer');
        const top = fila.getBoundingClientRect().top;
        const footerHeight = footer ? footer.getBoundingClientRect().height : 0;
        const margenInferior = 24;
        const disponible = window.innerHeight - top - footerHeight - margenInferior;
        fila.style.minHeight = Math.max(disponible, 420) + 'px';
      }

      document.addEventListener('DOMContentLoaded', () => {
        renderTabla();
        renderPerfil();
        renderPermisos();
        ajustarAlturaFilaCompleta();

        let resizeTimeout;
        window.addEventListener('resize', () => {
          clearTimeout(resizeTimeout);
          resizeTimeout = setTimeout(ajustarAlturaFilaCompleta, 150);
        });

        ['f-buscar', 'f-rol', 'f-estado', 'f-ultimo-acceso', 'f-antiguedad'].forEach((id) => {
          const el = document.getElementById(id);
          el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('btn-limpiar-filtros').addEventListener('click', () => {
          document.getElementById('f-buscar').value = '';
          document.getElementById('f-rol').value = '';
          document.getElementById('f-estado').value = '';
          document.getElementById('f-ultimo-acceso').value = '';
          document.getElementById('f-antiguedad').value = '';
          paginaActual = 1;
          renderTabla();
        });

        document.getElementById('btn-guardar-permisos').addEventListener('click', function () {
          const icon = this.querySelector('i');
          const original = icon.className;
          icon.className = 'bi bi-check-lg me-1';
          setTimeout(() => {
            icon.className = original;
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalRolesPermisos')).hide();
          }, 700);
        });

        // Validacion simple de contrasenas en el modal Nuevo Usuario
        const pass = document.getElementById('nu-password');
        const passConfirm = document.getElementById('nu-password-confirm');
        const form = document.getElementById('form-nuevo-usuario');
        form.addEventListener('submit', (e) => {
          e.preventDefault();
          if (pass.value !== passConfirm.value) {
            passConfirm.classList.add('is-invalid');
            return;
          }
          passConfirm.classList.remove('is-invalid');
          bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNuevoUsuario')).hide();
          form.reset();
        });
        passConfirm.addEventListener('input', () => passConfirm.classList.remove('is-invalid'));
      });
    
