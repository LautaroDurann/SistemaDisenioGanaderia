      const SELECTOR_SIDEBAR_WRAPPER = '.sidebar-wrapper';
      const Default = {
        scrollbarTheme: 'os-theme-light',
        scrollbarAutoHide: 'leave',
        scrollbarClickScroll: true,
      };
      document.addEventListener('DOMContentLoaded', function () {
        const sidebarWrapper = document.querySelector(SELECTOR_SIDEBAR_WRAPPER);
        const isMobile = window.innerWidth <= 992;
        if (
          sidebarWrapper &&
          OverlayScrollbarsGlobal?.OverlayScrollbars !== undefined &&
          !isMobile
        ) {
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
      // MOCK DATA: reemplazar por datos reales cuando se conecte con Django
      // ------------------------------------------------------------------
      const MOVIMIENTOS = window.HUACAPP_DATA?.movimientos ?? [
        { fecha: '2026-07-14', hora: '09:15', tipo: 'Ingreso', caravana: '0231', animal: 'Luna', categoria: 'Vaca', cantidad: 1, origen: 'La Esperanza', destino: 'Potrero 1', usuario: 'Juan', obs: 'Compra a establecimiento La Esperanza', estado: 'Confirmado' },
        { fecha: '2026-07-13', hora: '17:40', tipo: 'Venta', caravana: '0198', animal: 'Fierro', categoria: 'Toro', cantidad: 1, origen: 'Potrero 2', destino: 'Feria local', usuario: 'Carlos', obs: 'Vendido en remate feria local', estado: 'Confirmado' },
        { fecha: '2026-07-12', hora: '08:05', tipo: 'Nacimiento', caravana: '0305', animal: 'S/N', categoria: 'Ternero', cantidad: 1, origen: '-', destino: 'Potrero 2', usuario: 'María', obs: 'Nacimiento en Potrero 2', estado: 'Confirmado' },
        { fecha: '2026-07-10', hora: '12:30', tipo: 'Muerte', caravana: '0142', animal: 'Estrella', categoria: 'Vaca', cantidad: 1, origen: 'Potrero 3', destino: '-', usuario: 'Carlos', obs: 'Muerte por causas naturales', estado: 'Confirmado' },
        { fecha: '2026-07-10', hora: '10:00', tipo: 'Traslado', caravana: '0087', animal: 'S/N', categoria: 'Novillo', cantidad: 1, origen: 'Potrero 1', destino: 'Potrero 3', usuario: 'María', obs: 'Traslado por pastura', estado: 'Confirmado' },
        { fecha: '2026-07-09', hora: '15:20', tipo: 'Compra', caravana: '0056', animal: 'Paloma', categoria: 'Vaquillona', cantidad: 1, origen: 'Cabaña Norte', destino: 'Potrero 4', usuario: 'Juan', obs: 'Compra de reposición', estado: 'Pendiente' },
        { fecha: '2026-07-08', hora: '11:10', tipo: 'Alta', caravana: '0412', animal: 'S/N', categoria: 'Ternero', cantidad: 1, origen: '-', destino: 'Potrero 1', usuario: 'María', obs: 'Alta por nacimiento tardío', estado: 'Confirmado' },
        { fecha: '2026-07-06', hora: '09:45', tipo: 'Baja', caravana: '0329', animal: 'S/N', categoria: 'Novillo', cantidad: 1, origen: 'Potrero 1', destino: '-', usuario: 'Carlos', obs: 'Baja administrativa', estado: 'Confirmado' },
        { fecha: '2026-07-05', hora: '14:00', tipo: 'Traslado', caravana: '0263', animal: 'Rocío', categoria: 'Vaca', cantidad: 1, origen: 'Potrero 2', destino: 'Potrero 4', usuario: 'Juan', obs: 'Rotación de pastoreo', estado: 'Confirmado' },
        { fecha: '2026-07-03', hora: '08:50', tipo: 'Ingreso', caravana: '0177', animal: 'Trueno', categoria: 'Toro', cantidad: 1, origen: 'Cabaña Sur', destino: 'Potrero 4', usuario: 'María', obs: 'Ingreso por servicio', estado: 'Confirmado' },
        { fecha: '2026-07-01', hora: '16:15', tipo: 'Venta', caravana: '0301', animal: 'S/N', categoria: 'Novillo', cantidad: 3, origen: 'Potrero 3', destino: 'Frigorífico', usuario: 'Carlos', obs: 'Venta directa a frigorífico', estado: 'Confirmado' },
      ];

      const TIPO_BADGE = {
        Ingreso: 'text-bg-success',
        Venta: 'text-bg-danger',
        Muerte: 'badge-orange',
        Traslado: 'text-bg-primary',
        Nacimiento: 'badge-purple',
        Compra: 'text-bg-warning',
        Baja: 'text-bg-dark',
        Alta: 'text-bg-success',
      };

      const TIPO_ICON = {
        Ingreso: 'bi-box-arrow-in-down',
        Venta: 'bi-cash-coin',
        Muerte: 'bi-heartbreak',
        Traslado: 'bi-signpost-split',
        Nacimiento: 'bi-emoji-smile',
        Compra: 'bi-bag-check',
        Baja: 'bi-dash-circle',
        Alta: 'bi-plus-circle',
      };

      const FILAS_POR_PAGINA = 6;
      let paginaActual = 1;

      function formatFecha(iso) {
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y}`;
      }

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const desde = document.getElementById('f-desde').value;
        const hasta = document.getElementById('f-hasta').value;
        const tipo = document.getElementById('f-tipo').value;
        const categoria = document.getElementById('f-categoria').value;
        const potrero = document.getElementById('f-potrero').value;
        const usuario = document.getElementById('f-usuario').value;
        const estado = document.getElementById('f-estado').value;

        return MOVIMIENTOS.filter((m) => {
          const matchBuscar =
            !buscar ||
            m.caravana.toLowerCase().includes(buscar) ||
            m.animal.toLowerCase().includes(buscar) ||
            m.obs.toLowerCase().includes(buscar);
          const matchDesde = !desde || m.fecha >= desde;
          const matchHasta = !hasta || m.fecha <= hasta;
          const matchPotrero = !potrero || m.origen === potrero || m.destino === potrero;
          return (
            matchBuscar &&
            matchDesde &&
            matchHasta &&
            matchPotrero &&
            (!tipo || m.tipo === tipo) &&
            (!categoria || m.categoria === categoria) &&
            (!usuario || m.usuario === usuario) &&
            (!estado || m.estado === estado)
          );
        }).sort((a, b) => (a.fecha + a.hora < b.fecha + b.hora ? 1 : -1));
      }

      function renderTabla() {
        const datos = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

        const tbody = document.getElementById('tabla-mov-body');
        tbody.innerHTML = pagina
          .map(
            (m) => `
          <tr>
            <td>${formatFecha(m.fecha)}<br><small class="text-secondary">${m.hora}</small></td>
            <td><span class="badge ${TIPO_BADGE[m.tipo] || 'text-bg-secondary'}">${m.tipo}</span></td>
            <td>#${m.caravana}</td>
            <td>${m.animal}</td>
            <td>${m.categoria}</td>
            <td>${m.cantidad}</td>
            <td>${m.origen}</td>
            <td>${m.destino}</td>
            <td>${m.usuario}</td>
            <td class="text-truncate" style="max-width: 220px" title="${m.obs}">${m.obs}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary" title="Ver detalle"><i class="bi bi-eye"></i></button>
              <button class="btn btn-sm btn-outline-primary" title="Editar"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-dark" title="Imprimir comprobante"><i class="bi bi-printer"></i></button>
            </td>
          </tr>`,
          )
          .join('');

        document.getElementById('tabla-info').textContent = datos.length
          ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} movimientos`
          : 'Sin resultados para los filtros aplicados';

        const paginacion = document.getElementById('tabla-paginacion');
        paginacion.innerHTML = Array.from({ length: totalPaginas }, (_, i) => i + 1)
          .map(
            (p) => `
          <li class="page-item ${p === paginaActual ? 'active' : ''}">
            <button class="page-link" data-pagina="${p}">${p}</button>
          </li>`,
          )
          .join('');

        paginacion.querySelectorAll('[data-pagina]').forEach((btn) => {
          btn.addEventListener('click', () => {
            paginaActual = parseInt(btn.dataset.pagina, 10);
            renderTabla();
          });
        });
      }

      function actualizarKpis() {
        document.getElementById('kpi-total').textContent = MOVIMIENTOS.length;
        document.getElementById('kpi-ingresos').textContent = MOVIMIENTOS.filter((m) => m.tipo === 'Ingreso').length;
        document.getElementById('kpi-salidas').textContent = MOVIMIENTOS.filter((m) => m.tipo === 'Venta').length;
        document.getElementById('kpi-traslados').textContent = MOVIMIENTOS.filter((m) => m.tipo === 'Traslado').length;
        document.getElementById('kpi-nacimientos').textContent = MOVIMIENTOS.filter((m) => m.tipo === 'Nacimiento').length;
        document.getElementById('kpi-muertes').textContent = MOVIMIENTOS.filter((m) => m.tipo === 'Muerte').length;
      }

      function renderTimeline() {
        const ultimos = [...MOVIMIENTOS]
          .sort((a, b) => (a.fecha + a.hora < b.fecha + b.hora ? 1 : -1))
          .slice(0, 4);

        document.getElementById('timeline-container').innerHTML = ultimos
          .map((m) => {
            const badgeClass = TIPO_BADGE[m.tipo] || 'text-bg-secondary';
            const iconClass = TIPO_ICON[m.tipo] || 'bi-dot';
            const dotBg = badgeClass.startsWith('badge-')
              ? badgeClass
              : badgeClass.replace('text-bg-', 'bg-');
            return `
          <div class="vacapp-timeline-item">
            <div class="vacapp-timeline-dot ${dotBg}">
              <i class="bi ${iconClass}"></i>
            </div>
            <div class="d-flex justify-content-between flex-wrap">
              <div>
                <span class="badge ${badgeClass} me-2">${m.tipo}</span>
                <strong>#${m.caravana} ${m.animal}</strong>
                <div class="small text-secondary">${m.obs}</div>
              </div>
              <div class="text-end small text-secondary">
                ${formatFecha(m.fecha)} ${m.hora}<br />
                <span>Resp: ${m.usuario}</span>
              </div>
            </div>
          </div>`;
          })
          .join('');
      }

      // ------------------------------------------------------------------
      // Mini calendario (Julio 2026) con conteo de movimientos por dia
      // ------------------------------------------------------------------
      function renderCalendario() {
        const anio = 2026;
        const mes = 6; // Julio (0-indexado)
        const primerDia = new Date(anio, mes, 1).getDay(); // 0=domingo
        const diasEnMes = new Date(anio, mes + 1, 0).getDate();

        const conteoPorDia = {};
        MOVIMIENTOS.forEach((m) => {
          conteoPorDia[m.fecha] = (conteoPorDia[m.fecha] || 0) + 1;
        });

        const nombreMes = new Date(anio, mes, 1).toLocaleDateString('es-AR', {
          month: 'long',
          year: 'numeric',
        });
        document.getElementById('calendario-titulo').textContent =
          'Calendario - ' + nombreMes.charAt(0).toUpperCase() + nombreMes.slice(1);

        const etiquetas = ['D', 'L', 'M', 'M', 'J', 'V', 'S'];
        let html = etiquetas.map((e) => `<div class="day-label">${e}</div>`).join('');

        for (let i = 0; i < primerDia; i++) {
          html += `<div class="day-cell empty"></div>`;
        }

        for (let dia = 1; dia <= diasEnMes; dia++) {
          const fechaIso = `${anio}-${String(mes + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
          const cantidad = conteoPorDia[fechaIso] || 0;
          html += `
          <button type="button" class="day-cell ${cantidad ? 'has-events' : ''}" data-fecha="${fechaIso}">
            <span>${dia}</span>
            ${cantidad ? `<span class="dot-count">${cantidad}</span>` : ''}
          </button>`;
        }

        const grid = document.getElementById('calendario-grid');
        grid.innerHTML = html;

        grid.querySelectorAll('.day-cell[data-fecha]').forEach((cell) => {
          cell.addEventListener('click', () => {
            grid.querySelectorAll('.day-cell').forEach((c) => c.classList.remove('selected'));
            cell.classList.add('selected');
            mostrarMovimientosDelDia(cell.dataset.fecha);
          });
        });
      }

      function mostrarMovimientosDelDia(fechaIso) {
        const delDia = MOVIMIENTOS.filter((m) => m.fecha === fechaIso);
        const detalle = document.getElementById('calendario-detalle');
        if (!delDia.length) {
          detalle.innerHTML = `Sin movimientos el ${formatFecha(fechaIso)}.`;
          return;
        }
        detalle.innerHTML = `
          <strong class="d-block mb-1">${formatFecha(fechaIso)}</strong>
          <ul class="list-unstyled mb-0">
            ${delDia
              .map(
                (m) => `
              <li class="mb-1">
                <span class="badge ${TIPO_BADGE[m.tipo] || 'text-bg-secondary'}">${m.tipo}</span>
                #${m.caravana} ${m.animal}
              </li>`,
              )
              .join('')}
          </ul>`;
      }

      document.addEventListener('DOMContentLoaded', () => {
        actualizarKpis();
        renderTimeline();
        renderTabla();
        renderCalendario();

        ['f-buscar', 'f-desde', 'f-hasta', 'f-tipo', 'f-categoria', 'f-potrero', 'f-usuario', 'f-estado'].forEach(
          (id) => {
            document.getElementById(id).addEventListener('input', () => {
              paginaActual = 1;
              renderTabla();
            });
          },
        );

        document.getElementById('f-limpiar').addEventListener('click', () => {
          ['f-buscar', 'f-desde', 'f-hasta', 'f-tipo', 'f-categoria', 'f-potrero', 'f-usuario', 'f-estado'].forEach(
            (id) => {
              document.getElementById(id).value = '';
            },
          );
          paginaActual = 1;
          renderTabla();
        });
      });
    
