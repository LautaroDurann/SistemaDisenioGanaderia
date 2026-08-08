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
      const ALIMENTOS = window.GANASTOCK_DATA?.alimentos ?? [
        { id: 'balanceado-engorde', nombre: 'Balanceado Engorde', categoria: 'Balanceado', stock: 3200, unidad: 'kg', consumoMensual: 1800, stockMinimo: 1000, ultimaCompra: '05/07/2026', precioUnitario: 450 },
        { id: 'maiz-grano', nombre: 'Maíz grano', categoria: 'Maíz', stock: 850, unidad: 'kg', consumoMensual: 1200, stockMinimo: 1000, ultimaCompra: '20/06/2026', precioUnitario: 320 },
        { id: 'rollos-alfalfa', nombre: 'Rollos de alfalfa', categoria: 'Rollos', stock: 45, unidad: 'rollos', consumoMensual: 60, stockMinimo: 30, ultimaCompra: '01/07/2026', precioUnitario: 18000 },
        { id: 'silaje-maiz', nombre: 'Silaje de maíz', categoria: 'Silaje', stock: 12000, unidad: 'kg', consumoMensual: 9000, stockMinimo: 5000, ultimaCompra: '15/05/2026', precioUnitario: 90 },
        { id: 'pastura-diferida', nombre: 'Pastura diferida P.4', categoria: 'Pastura', stock: 25, unidad: 'ha', consumoMensual: 6, stockMinimo: 10, ultimaCompra: '-', precioUnitario: 0 },
        { id: 'suplemento-mineral', nombre: 'Suplemento mineral', categoria: 'Suplementos', stock: 180, unidad: 'kg', consumoMensual: 220, stockMinimo: 150, ultimaCompra: '10/06/2026', precioUnitario: 1200 },
        { id: 'sal-comun', nombre: 'Sal común', categoria: 'Otros', stock: 0, unidad: 'kg', consumoMensual: 40, stockMinimo: 50, ultimaCompra: '02/05/2026', precioUnitario: 150 },
        { id: 'rollos-moha', nombre: 'Rollos de moha', categoria: 'Rollos', stock: 15, unidad: 'rollos', consumoMensual: 25, stockMinimo: 20, ultimaCompra: '18/06/2026', precioUnitario: 16500 },
        { id: 'balanceado-recria', nombre: 'Balanceado Recría', categoria: 'Balanceado', stock: 900, unidad: 'kg', consumoMensual: 700, stockMinimo: 400, ultimaCompra: '28/02/2026', precioUnitario: 470, vencePronto: true },
        { id: 'expeller-soja', nombre: 'Expeller de soja', categoria: 'Suplementos', stock: 600, unidad: 'kg', consumoMensual: 500, stockMinimo: 300, ultimaCompra: '22/06/2026', precioUnitario: 380 },
      ];

      function estadoAlimento(a) {
        if (a.stock === 0) return 'Agotado';
        if (a.vencePronto) return 'Próximo a vencer';
        if (a.stock < a.stockMinimo) return 'Stock Bajo';
        return 'Disponible';
      }

      const ESTADO_BADGE = {
        Disponible: 'text-bg-success',
        'Stock Bajo': 'text-bg-warning',
        Agotado: 'text-bg-danger',
        'Próximo a vencer': 'text-bg-secondary',
      };

      // Evolucion de stock (6 puntos) y movimientos por alimento, para el modal de detalle
      const STOCK_EVOLUCION = {
        'balanceado-engorde': [2600, 3400, 2900, 3600, 3000, 3200],
        'maiz-grano': [1400, 1100, 1500, 900, 1300, 850],
        'rollos-alfalfa': [50, 55, 40, 60, 48, 45],
        'silaje-maiz': [15000, 13500, 16000, 12500, 13800, 12000],
        'pastura-diferida': [30, 28, 27, 26, 25, 25],
        'suplemento-mineral': [250, 220, 260, 200, 195, 180],
        'sal-comun': [80, 60, 50, 30, 15, 0],
        'rollos-moha': [30, 28, 22, 20, 18, 15],
        'balanceado-recria': [1200, 1100, 1000, 950, 920, 900],
        'expeller-soja': [700, 650, 680, 620, 610, 600],
      };

      const MOVIMIENTOS = {
        'balanceado-engorde': [
          { fecha: '05/07/2026', tipo: 'Compra', cantidad: '+1500 kg', responsable: 'Juan', obs: 'Reposición mensual' },
          { fecha: '28/06/2026', tipo: 'Consumo', cantidad: '-420 kg', responsable: 'María', obs: 'Racion Potrero 1' },
          { fecha: '15/06/2026', tipo: 'Consumo', cantidad: '-380 kg', responsable: 'Carlos', obs: 'Racion Potrero 2' },
        ],
        'maiz-grano': [
          { fecha: '20/06/2026', tipo: 'Compra', cantidad: '+600 kg', responsable: 'Carlos', obs: 'Proveedor La Norteña' },
          { fecha: '10/06/2026', tipo: 'Consumo', cantidad: '-300 kg', responsable: 'Juan', obs: 'Racion Potrero 3' },
          { fecha: '01/06/2026', tipo: 'Ajuste', cantidad: '-20 kg', responsable: 'María', obs: 'Corrección de inventario' },
        ],
        'rollos-alfalfa': [
          { fecha: '01/07/2026', tipo: 'Compra', cantidad: '+20 rollos', responsable: 'Juan', obs: 'Compra a productor local' },
          { fecha: '10/06/2026', tipo: 'Consumo', cantidad: '-8 rollos', responsable: 'Carlos', obs: 'Rodeo general' },
          { fecha: '02/06/2026', tipo: 'Perdida', cantidad: '-2 rollos', responsable: 'María', obs: 'Humedad, descarte' },
        ],
        'silaje-maiz': [
          { fecha: '15/05/2026', tipo: 'Compra', cantidad: '+8000 kg', responsable: 'Carlos', obs: 'Cosecha propia' },
          { fecha: '20/06/2026', tipo: 'Consumo', cantidad: '-3200 kg', responsable: 'Juan', obs: 'Racion invernal' },
        ],
        'pastura-diferida': [
          { fecha: '01/06/2026', tipo: 'Ajuste', cantidad: '-1 ha', responsable: 'María', obs: 'Reducción por sequía' },
        ],
        'suplemento-mineral': [
          { fecha: '10/06/2026', tipo: 'Compra', cantidad: '+100 kg', responsable: 'Juan', obs: 'Proveedor habitual' },
          { fecha: '25/06/2026', tipo: 'Consumo', cantidad: '-120 kg', responsable: 'Carlos', obs: 'Suplementacion vacas' },
        ],
        'sal-comun': [
          { fecha: '02/05/2026', tipo: 'Compra', cantidad: '+80 kg', responsable: 'María', obs: 'Compra en acopio' },
          { fecha: '30/06/2026', tipo: 'Consumo', cantidad: '-80 kg', responsable: 'Juan', obs: 'Consumo total, sin reposición' },
        ],
        'rollos-moha': [
          { fecha: '18/06/2026', tipo: 'Compra', cantidad: '+10 rollos', responsable: 'Carlos', obs: 'Compra parcial' },
          { fecha: '05/07/2026', tipo: 'Consumo', cantidad: '-15 rollos', responsable: 'María', obs: 'Rodeo Potrero 4' },
        ],
        'balanceado-recria': [
          { fecha: '28/02/2026', tipo: 'Compra', cantidad: '+1200 kg', responsable: 'Juan', obs: 'Lote próximo a vencer' },
          { fecha: '20/06/2026', tipo: 'Consumo', cantidad: '-300 kg', responsable: 'Carlos', obs: 'Racion terneros' },
        ],
        'expeller-soja': [
          { fecha: '22/06/2026', tipo: 'Compra', cantidad: '+500 kg', responsable: 'María', obs: 'Proveedor La Norteña' },
          { fecha: '08/07/2026', tipo: 'Consumo', cantidad: '-400 kg', responsable: 'Juan', obs: 'Suplementacion recria' },
        ],
      };

      const MOVIMIENTO_BADGE = {
        Compra: 'text-bg-success',
        Consumo: 'text-bg-primary',
        Ajuste: 'text-bg-secondary',
        Perdida: 'text-bg-danger',
      };

      const PLAN_ALIMENTACION = [
        { categoria: 'Vacas', potrero: 'Potrero 1', alimento: 'Balanceado Engorde', cantidad: '4 kg/animal', horario: '07:00', responsable: 'Juan' },
        { categoria: 'Terneros', potrero: 'Potrero 2', alimento: 'Maíz grano', cantidad: '1.5 kg/animal', horario: '08:30', responsable: 'María' },
        { categoria: 'Toros', potrero: 'Potrero 4', alimento: 'Suplemento mineral', cantidad: '0.3 kg/animal', horario: '09:00', responsable: 'Juan' },
        { categoria: 'Novillos', potrero: 'Potrero 3', alimento: 'Silaje de maiz', cantidad: '8 kg/animal', horario: '16:00', responsable: 'Carlos' },
        { categoria: 'Vaquillonas', potrero: 'Potrero 4', alimento: 'Expeller de soja', cantidad: '2 kg/animal', horario: '16:30', responsable: 'Carlos' },
        { categoria: 'Vacas', potrero: 'Potrero 2', alimento: 'Rollos de alfalfa', cantidad: '6 kg/animal', horario: '17:00', responsable: 'María' },
        { categoria: 'Terneros', potrero: 'Potrero 1', alimento: 'Balanceado Recría', cantidad: '1 kg/animal', horario: '08:00', responsable: 'Juan' },
        { categoria: 'Novillos', potrero: 'Potrero 3', alimento: 'Pastura diferida P.4', cantidad: 'A campo', horario: 'Todo el dia', responsable: 'Carlos' },
        { categoria: 'Toros', potrero: 'Potrero 2', alimento: 'Rollos de moha', cantidad: '5 kg/animal', horario: '17:30', responsable: 'Juan' },
      ];

      const FILAS_POR_PAGINA = 10;
      let paginaActual = 1;

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const categoria = document.getElementById('f-categoria').value;
        const estado = document.getElementById('f-estado').value;
        const unidad = document.getElementById('f-unidad').value;

        return ALIMENTOS.filter((a) => {
          const matchBuscar = !buscar || a.nombre.toLowerCase().includes(buscar);
          return (
            matchBuscar &&
            (!categoria || a.categoria === categoria) &&
            (!estado || estadoAlimento(a) === estado) &&
            (!unidad || a.unidad === unidad)
          );
        });
      }

      function renderTabla() {
        const datos = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

        document.getElementById('tabla-alimentos-body').innerHTML = pagina
          .map((a) => {
            const estado = estadoAlimento(a);
            return `
          <tr>
            <td>${a.nombre}</td>
            <td>${a.categoria}</td>
            <td>${a.stock} ${a.unidad}</td>
            <td>${a.unidad}</td>
            <td>${a.consumoMensual} ${a.unidad}</td>
            <td>${a.stockMinimo} ${a.unidad}</td>
            <td>${a.ultimaCompra}</td>
            <td><span class="badge ${ESTADO_BADGE[estado]}">${estado}</span></td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary btn-ver-detalle" data-id="${a.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
              <button class="btn btn-sm btn-outline-primary" title="Editar"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-success btn-consumo-rapido" data-id="${a.id}" title="Registrar consumo"><i class="bi bi-dash-circle"></i></button>
              <button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
            </td>
          </tr>`;
          })
          .join('');

        document.getElementById('tabla-info').textContent = datos.length
          ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} alimentos`
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

      function renderKpis() {
        document.getElementById('kpi-alimentos').textContent = ALIMENTOS.length;
        const stockBajo = ALIMENTOS.filter((a) => ['Stock Bajo', 'Agotado'].includes(estadoAlimento(a))).length;
        document.getElementById('kpi-stock-bajo').textContent = stockBajo;
      }

      function renderPlan() {
        document.getElementById('tabla-plan-body').innerHTML = PLAN_ALIMENTACION.map(
          (p) => `
          <tr>
            <td>${p.categoria}</td>
            <td>${p.potrero}</td>
            <td>${p.alimento}</td>
            <td>${p.cantidad}</td>
            <td>${p.horario}</td>
            <td>${p.responsable}</td>
          </tr>`,
        ).join('');
      }

      function renderSelectsAlimento() {
        const opciones = ALIMENTOS.map((a) => `<option value="${a.id}">${a.nombre}</option>`).join('');
        document.getElementById('consumo-alimento').innerHTML = opciones;
        document.getElementById('compra-alimento').innerHTML = opciones;
      }

      function actualizarInfoConsumo() {
        const id = document.getElementById('consumo-alimento').value;
        const a = ALIMENTOS.find((x) => x.id === id);
        document.getElementById('consumo-unidad').value = a.unidad;
        document.getElementById('consumo-alimento-stock').textContent = `Stock disponible: ${a.stock} ${a.unidad}`;
        calcularConsumo();
      }

      function calcularConsumo() {
        const id = document.getElementById('consumo-alimento').value;
        const a = ALIMENTOS.find((x) => x.id === id);
        const cantidad = parseFloat(document.getElementById('consumo-cantidad').value) || 0;
        const resultante = a.stock - cantidad;
        const el = document.getElementById('consumo-calc-resultante');
        el.textContent = `${resultante} ${a.unidad}`;
        el.className = resultante < 0 ? 'fw-semibold text-danger' : resultante < a.stockMinimo ? 'fw-semibold text-warning' : 'fw-semibold text-success';
      }

      function calcularCompra() {
        const cantidad = parseFloat(document.getElementById('compra-cantidad').value) || 0;
        const precioUnitario = parseFloat(document.getElementById('compra-precio-unitario').value) || 0;
        document.getElementById('compra-precio-total').value = (cantidad * precioUnitario).toLocaleString('es-AR');
      }

      let chartDetalle = null;
      function abrirDetalle(id) {
        const a = ALIMENTOS.find((x) => x.id === id);
        const estado = estadoAlimento(a);

        document.getElementById('detalle-alimento-nombre').textContent = a.nombre;
        document.getElementById('detalle-alimento-info').innerHTML = `
          <div class="col-md-4"><small class="text-secondary d-block">Categoría</small><strong>${a.categoria}</strong></div>
          <div class="col-md-4"><small class="text-secondary d-block">Stock actual</small><strong>${a.stock} ${a.unidad}</strong></div>
          <div class="col-md-4"><small class="text-secondary d-block">Stock mínimo</small><strong>${a.stockMinimo} ${a.unidad}</strong></div>
          <div class="col-md-4"><small class="text-secondary d-block">Precio unitario</small><strong>${a.precioUnitario ? '$ ' + a.precioUnitario.toLocaleString('es-AR') : '-'}</strong></div>
          <div class="col-md-4"><small class="text-secondary d-block">Última compra</small><strong>${a.ultimaCompra}</strong></div>
          <div class="col-md-4"><small class="text-secondary d-block">Estado</small><span class="badge ${ESTADO_BADGE[estado]}">${estado}</span></div>`;

        const serie = STOCK_EVOLUCION[a.id];
        const el = document.querySelector('#detalle-alimento-chart');
        el.innerHTML = '';
        chartDetalle = new ApexCharts(el, {
          series: [{ name: `Stock (${a.unidad})`, data: serie }],
          chart: { height: 200, type: 'line', toolbar: { show: false } },
          colors: ['#0d6efd'],
          stroke: { curve: 'smooth', width: 3 },
          markers: { size: 4 },
          dataLabels: { enabled: false },
          xaxis: { categories: ['-5m', '-4m', '-3m', '-2m', '-1m', 'Actual'] },
        });
        chartDetalle.render();

        document.getElementById('detalle-alimento-movimientos').innerHTML = (MOVIMIENTOS[a.id] || [])
          .map(
            (m) => `
          <tr>
            <td>${m.fecha}</td>
            <td><span class="badge ${MOVIMIENTO_BADGE[m.tipo] || 'text-bg-secondary'}">${m.tipo}</span></td>
            <td>${m.cantidad}</td>
            <td>${m.responsable}</td>
            <td>${m.obs}</td>
          </tr>`,
          )
          .join('');

        new bootstrap.Modal(document.getElementById('modalDetalleAlimento')).show();
      }

      document.addEventListener('DOMContentLoaded', () => {
        renderKpis();
        renderTabla();
        renderPlan();
        renderSelectsAlimento();

        // Grafico consumo mensual (barras) - mock 12 meses
        new ApexCharts(document.querySelector('#chart-consumo-mensual'), {
          series: [{ name: 'Consumo (kg)', data: [9800, 10200, 11000, 9500, 10800, 11500, 12000, 11800, 12600, 12300, 12100, 12600] }],
          chart: { height: 300, type: 'bar', toolbar: { show: false } },
          colors: ['#198754'],
          plotOptions: { bar: { borderRadius: 5, columnWidth: '55%' } },
          dataLabels: { enabled: false },
          xaxis: { categories: ['Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul'] },
        }).render();

        // Grafico distribucion del consumo (doughnut) - mock
        new ApexCharts(document.querySelector('#chart-distribucion-consumo'), {
          series: [32, 18, 14, 20, 6, 8, 2],
          chart: { height: 300, type: 'donut' },
          labels: ['Balanceado', 'Maíz', 'Rollos', 'Silaje', 'Pastura', 'Suplementos', 'Otros'],
          colors: ['#198754', '#0d6efd', '#ffc107', '#6c757d', '#20c997', '#6610f2', '#adb5bd'],
          legend: { position: 'bottom' },
        }).render();

        document.getElementById('tabla-alimentos-body').addEventListener('click', (ev) => {
          const btnDetalle = ev.target.closest('.btn-ver-detalle');
          if (btnDetalle) abrirDetalle(btnDetalle.dataset.id);

          const btnConsumo = ev.target.closest('.btn-consumo-rapido');
          if (btnConsumo) {
            document.getElementById('consumo-alimento').value = btnConsumo.dataset.id;
            actualizarInfoConsumo();
            new bootstrap.Modal(document.getElementById('modalRegistrarConsumo')).show();
          }
        });

        ['f-buscar', 'f-categoria', 'f-estado', 'f-unidad'].forEach((id) => {
          document.getElementById(id).addEventListener('input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('f-limpiar').addEventListener('click', () => {
          document.getElementById('f-buscar').value = '';
          document.getElementById('f-categoria').value = '';
          document.getElementById('f-estado').value = '';
          document.getElementById('f-unidad').value = '';
          paginaActual = 1;
          renderTabla();
        });

        document.getElementById('consumo-fecha').value = '2026-07-15';
        document.getElementById('consumo-hora').value = new Date().toTimeString().slice(0, 5);
        document.getElementById('consumo-alimento').addEventListener('change', actualizarInfoConsumo);
        document.getElementById('consumo-cantidad').addEventListener('input', calcularConsumo);
        document.getElementById('modalRegistrarConsumo').addEventListener('shown.bs.modal', actualizarInfoConsumo);
        document.getElementById('btn-guardar-consumo').addEventListener('click', () => {
          // Mock: aca va el POST real al conectar con Django.
          bootstrap.Modal.getInstance(document.getElementById('modalRegistrarConsumo')).hide();
        });

        document.getElementById('compra-fecha').value = '2026-07-15';
        document.getElementById('compra-cantidad').addEventListener('input', calcularCompra);
        document.getElementById('compra-precio-unitario').addEventListener('input', calcularCompra);
        document.getElementById('btn-guardar-compra').addEventListener('click', () => {
          // Mock: aca va el POST real al conectar con Django.
          bootstrap.Modal.getInstance(document.getElementById('modalRegistrarCompra')).hide();
        });
      });
    
