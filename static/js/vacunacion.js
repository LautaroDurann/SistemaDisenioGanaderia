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
      // Los animales/caravanas coinciden con los de Stock y Movimientos.
      // ------------------------------------------------------------------
      const VACUNACIONES = window.GANASTOCK_DATA?.vacunaciones ?? [
        { fecha: '2026-07-14', caravana: '0231', animal: 'Luna', categoria: 'Vaca', edad: '4 años', potrero: 'Potrero 1', vacuna: 'Aftosa', proxima: '14/01/2027', veterinario: 'Dr. Lopez', estado: 'Vacunado', obs: 'Sin reacciones' },
        { fecha: '2026-07-14', caravana: '0412', animal: 'S/N', categoria: 'Ternero', edad: '3 meses', potrero: 'Potrero 1', vacuna: 'Clostridiosis', proxima: '14/09/2026', veterinario: 'Dra. Gimenez', estado: 'Vacunado', obs: 'Primera dosis' },
        { fecha: '2026-07-10', caravana: '0198', animal: 'Fierro', categoria: 'Toro', edad: '5 años', potrero: 'Potrero 2', vacuna: 'Brucelosis', proxima: '10/07/2027', veterinario: 'Dr. Lopez', estado: 'Vacunado', obs: '-' },
        { fecha: '2026-07-05', caravana: '0142', animal: 'Estrella', categoria: 'Vaca', edad: '6 años', potrero: 'Potrero 3', vacuna: 'Carbunclo', proxima: '05/01/2026', veterinario: 'Dra. Gimenez', estado: 'Vencido', obs: 'Requiere refuerzo urgente' },
        { fecha: '2026-07-20', caravana: '0087', animal: 'S/N', categoria: 'Novillo', edad: '2 años', potrero: 'Potrero 3', vacuna: 'Aftosa', proxima: '-', veterinario: 'Dr. Lopez', estado: 'Programado', obs: 'Campaña Aftosa Julio' },
        { fecha: '2026-07-22', caravana: '0056', animal: 'Paloma', categoria: 'Vaquillona', edad: '1 año', potrero: 'Potrero 4', vacuna: 'Rabia', proxima: '-', veterinario: 'Dra. Gimenez', estado: 'Pendiente', obs: 'Coordinar con establecimiento' },
        { fecha: '2026-06-28', caravana: '0177', animal: 'Trueno', categoria: 'Toro', edad: '3 años', potrero: 'Potrero 4', vacuna: 'Aftosa', proxima: '28/12/2026', veterinario: 'Dr. Lopez', estado: 'Vacunado', obs: '-' },
        { fecha: '2026-07-16', caravana: '0263', animal: 'Rocio', categoria: 'Vaca', edad: '5 años', potrero: 'Potrero 2', vacuna: 'Brucelosis', proxima: '-', veterinario: 'Dra. Gimenez', estado: 'Pendiente', obs: 'Reprogramar' },
        { fecha: '2026-06-15', caravana: '0329', animal: 'S/N', categoria: 'Novillo', edad: '2 años', potrero: 'Potrero 1', vacuna: 'Carbunclo', proxima: '15/12/2026', veterinario: 'Dr. Lopez', estado: 'Vacunado', obs: '-' },
        { fecha: '2026-07-08', caravana: '0305', animal: 'S/N', categoria: 'Ternero', edad: '2 meses', potrero: 'Potrero 2', vacuna: 'Otras', proxima: '08/10/2026', veterinario: 'Dra. Gimenez', estado: 'Vacunado', obs: 'Vitaminas + antiparasitario' },
      ];

      const ESTADO_BADGE = {
        Vacunado: 'text-bg-success',
        Pendiente: 'text-bg-warning',
        Vencido: 'text-bg-danger',
        Programado: 'text-bg-primary',
      };

      const CAMPANAS = [
        { nombre: 'Campaña Aftosa Julio 2026', inicio: '01/07/2026', fin: '31/07/2026', vacunados: 180, pendientes: 80 },
        { nombre: 'Refuerzo Brucelosis Hembras', inicio: '15/06/2026', fin: '15/08/2026', vacunados: 90, pendientes: 40 },
      ];

      const FILAS_POR_PAGINA = 6;
      let paginaActual = 1;
      let animalSeleccionado = null;

      function formatFecha(iso) {
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y}`;
      }

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const fecha = document.getElementById('f-fecha').value;
        const vacuna = document.getElementById('f-vacuna').value;
        const categoria = document.getElementById('f-categoria').value;
        const potrero = document.getElementById('f-potrero').value;
        const estado = document.getElementById('f-estado').value;
        const veterinario = document.getElementById('f-veterinario').value;

        return VACUNACIONES.filter((v) => {
          const matchBuscar =
            !buscar || v.caravana.toLowerCase().includes(buscar) || v.animal.toLowerCase().includes(buscar);
          return (
            matchBuscar &&
            (!fecha || v.fecha === fecha) &&
            (!vacuna || v.vacuna === vacuna) &&
            (!categoria || v.categoria === categoria) &&
            (!potrero || v.potrero === potrero) &&
            (!estado || v.estado === estado) &&
            (!veterinario || v.veterinario === veterinario)
          );
        }).sort((a, b) => (a.fecha < b.fecha ? 1 : -1));
      }

      function renderTabla() {
        const datos = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

        document.getElementById('tabla-vac-body').innerHTML = pagina
          .map(
            (v) => `
          <tr>
            <td>${formatFecha(v.fecha)}</td>
            <td>#${v.caravana}</td>
            <td>${v.animal}</td>
            <td>${v.categoria}</td>
            <td>${v.vacuna}</td>
            <td>${v.proxima}</td>
            <td>${v.veterinario}</td>
            <td><span class="badge ${ESTADO_BADGE[v.estado] || 'text-bg-secondary'}">${v.estado}</span></td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary btn-ver-vac" data-caravana="${v.caravana}" title="Ver detalle"><i class="bi bi-eye"></i></button>
              <button class="btn btn-sm btn-outline-primary" title="Editar"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-dark" title="Imprimir certificado"><i class="bi bi-printer"></i></button>
            </td>
          </tr>`,
          )
          .join('');

        document.getElementById('tabla-info').textContent = datos.length
          ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} registros`
          : 'Sin resultados para los filtros aplicados';

        const paginacion = document.getElementById('tabla-paginacion');
        paginacion.innerHTML = Array.from({ length: totalPaginas }, (_, i) => i + 1)
          .map((p) => `<li class="page-item ${p === paginaActual ? 'active' : ''}"><button class="page-link" data-pagina="${p}">${p}</button></li>`)
          .join('');
        paginacion.querySelectorAll('[data-pagina]').forEach((btn) => {
          btn.addEventListener('click', () => {
            paginaActual = parseInt(btn.dataset.pagina, 10);
            renderTabla();
          });
        });
      }

      function renderDetalleAnimal(caravana) {
        const registros = VACUNACIONES.filter((v) => v.caravana === caravana).sort((a, b) => (a.fecha < b.fecha ? 1 : -1));
        if (!registros.length) return;
        const base = registros[0];
        animalSeleccionado = caravana;

        document.getElementById('detalle-animal-nombre').textContent = `${base.animal} (#${base.caravana})`;
        document.getElementById('detalle-caravana').textContent = `#${base.caravana}`;
        document.getElementById('detalle-edad').textContent = base.edad;
        document.getElementById('detalle-potrero').textContent = base.potrero;
        document.getElementById('detalle-estado-sanitario').textContent = registros.some((r) => r.estado === 'Vencido')
          ? 'Con vacunas vencidas'
          : 'Al dia';

        document.getElementById('detalle-historial').innerHTML = registros
          .map(
            (r) => `
          <tr>
            <td>${r.vacuna}</td>
            <td>${formatFecha(r.fecha)}</td>
            <td>${r.proxima}</td>
            <td>${r.veterinario}</td>
            <td>${r.obs}</td>
          </tr>`,
          )
          .join('');

        const modalDetalle = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalDetalleAnimal'));
        modalDetalle.show();
      }

      function actualizarKpisYAlertas() {
        const aplicadas = VACUNACIONES.filter((v) => v.estado === 'Vacunado').length;
        const esteMes = VACUNACIONES.filter((v) => v.estado === 'Vacunado' && v.fecha.startsWith('2026-07')).length;
        const proximas = VACUNACIONES.filter((v) => v.estado === 'Pendiente' || v.estado === 'Programado').length;

        document.getElementById('kpi-aplicadas').textContent = aplicadas;
        document.getElementById('kpi-mes').textContent = esteMes;
        document.getElementById('kpi-proximas').textContent = proximas;
        document.getElementById('kpi-campanas').textContent = CAMPANAS.length;
      }

      function renderCampanas() {
        document.getElementById('campanas-lista').innerHTML = CAMPANAS.map((c) => {
          const total = c.vacunados + c.pendientes;
          const progreso = total ? Math.round((c.vacunados / total) * 100) : 0;
          return `
          <div>
            <div class="d-flex justify-content-between flex-wrap mb-1">
              <strong>${c.nombre}</strong>
              <small class="text-secondary">${c.inicio} - ${c.fin}</small>
            </div>
            <div class="d-flex justify-content-between small text-secondary mb-1">
              <span>${c.vacunados} vacunados / ${c.pendientes} pendientes</span>
              <span>${progreso}%</span>
            </div>
            <div class="progress" style="height: 8px">
              <div class="progress-bar bg-success" style="width: ${progreso}%"></div>
            </div>
          </div>`;
        }).join('');
      }

      // ------------------------------------------------------------------
      // Calendario sanitario (Julio 2026)
      // ------------------------------------------------------------------
      function renderCalendario() {
        const anio = 2026;
        const mes = 6; // Julio
        const primerDia = new Date(anio, mes, 1).getDay();
        const diasEnMes = new Date(anio, mes + 1, 0).getDate();

        const conteoPorDia = {};
        VACUNACIONES.forEach((v) => {
          conteoPorDia[v.fecha] = (conteoPorDia[v.fecha] || 0) + 1;
        });

        const nombreMes = new Date(anio, mes, 1).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });
        document.getElementById('calendario-titulo').textContent =
          'Calendario sanitario - ' + nombreMes.charAt(0).toUpperCase() + nombreMes.slice(1);

        const etiquetas = ['D', 'L', 'M', 'M', 'J', 'V', 'S'];
        let html = etiquetas.map((e) => `<div class="day-label">${e}</div>`).join('');

        for (let i = 0; i < primerDia; i++) html += `<div class="day-cell empty"></div>`;

        for (let dia = 1; dia <= diasEnMes; dia++) {
          const fechaIso = `${anio}-${String(mes + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
          const cantidad = conteoPorDia[fechaIso] || 0;
          html += `
          <button type="button" class="day-cell ${cantidad ? 'has-events' : ''}" data-fecha="${fechaIso}">
            <span>${dia}</span>
            ${cantidad ? `<span class="dot-count">${cantidad} evento${cantidad > 1 ? 's' : ''}</span>` : ''}
          </button>`;
        }

        const grid = document.getElementById('calendario-grid');
        grid.innerHTML = html;

        grid.querySelectorAll('.day-cell[data-fecha]').forEach((cell) => {
          cell.addEventListener('click', () => {
            grid.querySelectorAll('.day-cell').forEach((c) => c.classList.remove('selected'));
            cell.classList.add('selected');
            mostrarVacunacionesDelDia(cell.dataset.fecha);
          });
        });
      }

      function mostrarVacunacionesDelDia(fechaIso) {
        const delDia = VACUNACIONES.filter((v) => v.fecha === fechaIso);
        const detalle = document.getElementById('calendario-detalle');
        if (!delDia.length) {
          detalle.innerHTML = `Sin eventos el ${formatFecha(fechaIso)}.`;
          return;
        }
        detalle.innerHTML = `
          <strong class="d-block mb-1">${formatFecha(fechaIso)}</strong>
          <ul class="list-unstyled mb-0">
            ${delDia
              .map((v) => `<li class="mb-1"><span class="badge ${ESTADO_BADGE[v.estado] || 'text-bg-secondary'}">${v.estado}</span> #${v.caravana} ${v.animal} - ${v.vacuna}</li>`)
              .join('')}
          </ul>`;
      }

      document.addEventListener('DOMContentLoaded', () => {
        actualizarKpisYAlertas();
        renderCalendario();
        renderTabla();
        renderCampanas();

        document.getElementById('tabla-vac-body').addEventListener('click', (ev) => {
          const btn = ev.target.closest('.btn-ver-vac');
          if (btn) renderDetalleAnimal(btn.dataset.caravana);
        });

        ['f-buscar', 'f-fecha', 'f-vacuna', 'f-categoria', 'f-potrero', 'f-estado', 'f-veterinario'].forEach((id) => {
          document.getElementById(id).addEventListener('input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('f-limpiar').addEventListener('click', () => {
          ['f-buscar', 'f-fecha', 'f-vacuna', 'f-categoria', 'f-potrero', 'f-estado', 'f-veterinario'].forEach((id) => {
            document.getElementById(id).value = '';
          });
          paginaActual = 1;
          renderTabla();
        });

        // "Programar Campaña" y el link de campañas activas llevan a la seccion de campañas
        document.getElementById('btn-programar-campana').addEventListener('click', () => {
          document.getElementById('campanas-sanitarias').scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
        document.getElementById('link-campanas').addEventListener('click', (e) => {
          e.preventDefault();
          document.getElementById('campanas-sanitarias').scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
      });
    
