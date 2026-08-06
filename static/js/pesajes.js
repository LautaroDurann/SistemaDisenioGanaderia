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
      const ANIMALES_PESAJE = window.GANASTOCK_DATA?.animales_pesaje ?? [
        { caravana: '0231', nombre: 'Luna', categoria: 'Vaca', potrero: 'Potrero 1', responsable: 'Juan' },
        { caravana: '0198', nombre: 'Fierro', categoria: 'Toro', potrero: 'Potrero 2', responsable: 'Carlos' },
        { caravana: '0305', nombre: 'S/N', categoria: 'Ternero', potrero: 'Potrero 2', responsable: 'Maria' },
        { caravana: '0142', nombre: 'Estrella', categoria: 'Vaca', potrero: 'Potrero 3', responsable: 'Carlos' },
        { caravana: '0087', nombre: 'S/N', categoria: 'Novillo', potrero: 'Potrero 3', responsable: 'Maria' },
        { caravana: '0056', nombre: 'Paloma', categoria: 'Vaquillona', potrero: 'Potrero 4', responsable: 'Juan' },
        { caravana: '0177', nombre: 'Trueno', categoria: 'Toro', potrero: 'Potrero 4', responsable: 'Juan' },
        { caravana: '0263', nombre: 'Rocio', categoria: 'Vaca', potrero: 'Potrero 2', responsable: 'Maria' },
      ];

      // Historial de peso por animal, orden cronologico ascendente
      const HISTORIAL = window.GANASTOCK_DATA?.historial ?? {
        '0231': [
          { fecha: '10/03/2026', peso: 455 },
          { fecha: '10/05/2026', peso: 465 },
          { fecha: '10/07/2026', peso: 480 },
        ],
        '0198': [
          { fecha: '01/03/2026', peso: 690 },
          { fecha: '01/05/2026', peso: 705 },
          { fecha: '01/07/2026', peso: 720 },
        ],
        '0305': [
          { fecha: '12/05/2026', peso: 60 },
          { fecha: '12/06/2026', peso: 72 },
          { fecha: '12/07/2026', peso: 85 },
        ],
        '0142': [
          { fecha: '15/01/2026', peso: 520 },
          { fecha: '15/04/2026', peso: 515 },
          { fecha: '15/07/2026', peso: 498 },
        ],
        '0087': [
          { fecha: '29/01/2026', peso: 340 },
          { fecha: '29/04/2026', peso: 365 },
          { fecha: '29/06/2026', peso: 390 },
        ],
        '0056': [
          { fecha: '18/01/2026', peso: 230 },
          { fecha: '18/04/2026', peso: 255 },
          { fecha: '18/07/2026', peso: 280 },
        ],
        '0177': [
          { fecha: '10/01/2026', peso: 650 },
          { fecha: '10/04/2026', peso: 670 },
        ],
        '0263': [
          { fecha: '07/02/2026', peso: 470 },
          { fecha: '07/05/2026', peso: 485 },
          { fecha: '07/07/2026', peso: 495 },
        ],
      };

      // Tabla de registros = ultimo pesaje de cada animal, con su comparativa contra el anterior
      let PESAJES = [];
      function reconstruirPesajes() {
        PESAJES = ANIMALES_PESAJE
          .map((a) => {
            const hist = HISTORIAL[a.id];
            if (!hist || !hist.length) return null;
            const actual = hist[hist.length - 1];
            const anterior = hist.length > 1 ? hist[hist.length - 2] : null;
            const diferencia = anterior ? actual.peso - anterior.peso : 0;
            const gpd = anterior ? diferencia / diasEntre(anterior.fecha, actual.fecha) : 0;
            return {
              ...a,
              fecha: actual.fecha,
              pesoActual: actual.peso,
              pesoAnterior: anterior ? anterior.peso : null,
              diferencia,
              gpd,
            };
          })
          .filter(Boolean)
          .sort((a, b) => aFechaISO(b.fecha).localeCompare(aFechaISO(a.fecha)));
      }
      reconstruirPesajes();

      function aFechaISO(fechaDDMMYYYY) {
        const [d, m, y] = fechaDDMMYYYY.split('/');
        return `${y}-${m}-${d}`;
      }
      function diasEntre(f1, f2) {
        const ms = new Date(aFechaISO(f2)) - new Date(aFechaISO(f1));
        return Math.max(1, Math.round(ms / 86400000));
      }

      const FILAS_POR_PAGINA = 10;
      let paginaActual = 1;
      let chartEvolucion = null;

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const categoria = document.getElementById('f-categoria').value;
        const potrero = document.getElementById('f-potrero').value;
        const responsable = document.getElementById('f-responsable').value;

        return PESAJES.filter((p) => {
          const matchBuscar =
            !buscar ||
            p.caravana.toLowerCase().includes(buscar) ||
            p.nombre.toLowerCase().includes(buscar);
          return (
            matchBuscar &&
            (!categoria || p.categoria === categoria) &&
            (!potrero || p.potrero === potrero) &&
            (!responsable || p.responsable === responsable)
          );
        });
      }

      function renderTabla() {
        const datos = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

        document.getElementById('tabla-pesajes-body').innerHTML = pagina
          .map((p) => {
            const difClase = p.diferencia > 0 ? 'text-success' : p.diferencia < 0 ? 'text-danger' : 'text-secondary';
            const difTexto = p.pesoAnterior === null ? '-' : `${p.diferencia > 0 ? '+' : ''}${p.diferencia} kg`;
            const gpdTexto = p.pesoAnterior === null ? '-' : `${p.gpd.toFixed(2)} kg/dia`;
            return `
          <tr>
            <td>${p.fecha}</td>
            <td>#${p.caravana}</td>
            <td>${p.nombre}</td>
            <td>${p.categoria}</td>
            <td>${p.pesoActual} kg</td>
            <td>${p.pesoAnterior !== null ? p.pesoAnterior + ' kg' : '-'}</td>
            <td class="${difClase} fw-semibold">${difTexto}</td>
            <td>${gpdTexto}</td>
            <td>${p.responsable}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary btn-ver-historial" data-id="${p.id}" title="Ver historial"><i class="bi bi-clock-history"></i></button>
              <button class="btn btn-sm btn-outline-primary" title="Editar"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
            </td>
          </tr>`;
          })
          .join('');

        document.getElementById('tabla-info').textContent = datos.length
          ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} registros`
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

      function renderKpis() {
        const totalPesajes = Object.values(HISTORIAL).reduce((acc, h) => acc + h.length, 0);
        const pesoPromedio = Math.round(PESAJES.reduce((acc, p) => acc + p.pesoActual, 0) / PESAJES.length);

        document.getElementById('kpi-total-pesajes').textContent = totalPesajes;
        document.getElementById('kpi-peso-promedio').textContent = `${pesoPromedio} kg`;
        document.getElementById('kpi-pendientes').textContent = '9';
      }

      function renderSelectAnimalChart() {
        const select = document.getElementById('select-animal-chart');
        select.innerHTML = ANIMALES_PESAJE.map((a) => `<option value="${a.id}">#${a.caravana} ${a.nombre}</option>`).join('');
        select.value = ANIMALES_PESAJE[0].id;
      }

      function renderSelectAnimalModal() {
        const select = document.getElementById('pesaje-animal');
        select.innerHTML = ANIMALES_PESAJE.map((a) => `<option value="${a.id}">#${a.caravana} ${a.nombre} - ${a.categoria}</option>`).join('');
      }

      function renderChartEvolucion(id) {
        const hist = HISTORIAL[id];
        const categorias = hist.map((h) => h.fecha);
        const pesos = hist.map((h) => h.peso);

        if (!chartEvolucion) {
          chartEvolucion = new ApexCharts(document.querySelector('#chart-evolucion-peso'), {
            series: [{ name: 'Peso (kg)', data: pesos }],
            chart: { height: 300, type: 'line', toolbar: { show: false } },
            colors: ['#198754'],
            stroke: { curve: 'smooth', width: 3 },
            markers: { size: 4 },
            dataLabels: { enabled: false },
            xaxis: { categories: categorias },
            yaxis: { labels: { formatter: (v) => `${v} kg` } },
          });
          chartEvolucion.render();
        } else {
          chartEvolucion.updateOptions({ xaxis: { categories: categorias } });
          chartEvolucion.updateSeries([{ name: 'Peso (kg)', data: pesos }]);
        }

        const primero = hist[0];
        const ultimo = hist[hist.length - 1];
        const gananciaTotal = ultimo.peso - primero.peso;
        const gpd = hist.length > 1 ? (gananciaTotal / diasEntre(primero.fecha, ultimo.fecha)).toFixed(2) : '-';
        document.getElementById('chart-evolucion-resumen').innerHTML = `
          <span><i class="bi bi-graph-up-arrow text-success me-1"></i>Ganancia total: <strong>${gananciaTotal > 0 ? '+' : ''}${gananciaTotal} kg</strong></span>
          <span><i class="bi bi-speedometer2 text-primary me-1"></i>GPD promedio: <strong>${gpd} kg/dia</strong></span>
          <span><i class="bi bi-calendar-range text-secondary me-1"></i>Periodo: ${primero.fecha} - ${ultimo.fecha}</span>`;
      }

      function renderChartCategoria() {
        new ApexCharts(document.querySelector('#chart-peso-categoria'), {
          series: [{ name: 'Peso promedio', data: [90, 275, 395, 490, 705] }],
          chart: { height: 300, type: 'bar', toolbar: { show: false } },
          colors: ['#0d6efd'],
          plotOptions: { bar: { borderRadius: 6, columnWidth: '55%' } },
          dataLabels: { enabled: false },
          xaxis: { categories: ['Terneros', 'Vaquillonas', 'Novillos', 'Vacas', 'Toros'] },
          yaxis: { labels: { formatter: (v) => `${v} kg` } },
        }).render();
      }

      function abrirHistorial(id) {
        const animal = ANIMALES_PESAJE.find((a) => a.id === id);
        const hist = [...HISTORIAL[id]].reverse();

        document.getElementById('historial-animal-nombre').textContent = `#${animal.caravana} ${animal.nombre}`;
        document.getElementById('historial-timeline').innerHTML = hist
          .map((h, idx) => {
            const anterior = hist[idx + 1];
            const dif = anterior ? h.peso - anterior.peso : null;
            const difTexto = dif === null ? 'Primer registro' : `${dif > 0 ? '+' : ''}${dif} kg vs registro anterior`;
            const difClase = dif === null ? 'text-secondary' : dif > 0 ? 'text-success' : dif < 0 ? 'text-danger' : 'text-secondary';
            return `
          <div class="vacapp-timeline-item">
            <div class="d-flex justify-content-between">
              <strong>${h.fecha}</strong>
              <span>${h.peso} kg</span>
            </div>
            <small class="${difClase}">${difTexto}</small><br />
            <small class="text-secondary">Responsable: ${animal.responsable}</small>
          </div>`;
          })
          .join('');

        new bootstrap.Modal(document.getElementById('modalHistorialPesajes')).show();
      }

      function actualizarInfoAnimalModal() {
        const id = Number(document.getElementById('pesaje-animal').value);
        const animal = ANIMALES_PESAJE.find((a) => a.id === id);
        const hist = HISTORIAL[id];
        const ultimo = hist[hist.length - 1];

        document.getElementById('pesaje-animal-categoria').textContent = animal.categoria;
        document.getElementById('pesaje-animal-ultimo').textContent = `${ultimo.peso} kg (${ultimo.fecha})`;
        document.getElementById('pesaje-peso').dataset.ultimoPeso = ultimo.peso;
        document.getElementById('pesaje-peso').dataset.ultimaFecha = ultimo.fecha;
        document.getElementById('pesaje-peso').dataset.primerPeso = hist[0].peso;
        document.getElementById('pesaje-peso').dataset.primeraFecha = hist[0].fecha;
        calcularPesaje();
      }

      function calcularPesaje() {
        const input = document.getElementById('pesaje-peso');
        const pesoActual = parseFloat(input.value);
        const ultimoPeso = parseFloat(input.dataset.ultimoPeso || 0);
        const primerPeso = parseFloat(input.dataset.primerPeso || 0);
        const fecha = document.getElementById('pesaje-fecha').value || '2026-07-15';

        if (!pesoActual) {
          document.getElementById('pesaje-calc-diferencia').textContent = '- kg';
          document.getElementById('pesaje-calc-gpd').textContent = '- kg/dia';
          document.getElementById('pesaje-calc-total').textContent = '- kg';
          return;
        }

        const diferencia = pesoActual - ultimoPeso;
        const ultimaFechaISO = aFechaISO(input.dataset.ultimaFecha || '15/07/2026');
        const dias = Math.max(1, Math.round((new Date(fecha) - new Date(ultimaFechaISO)) / 86400000));
        const gpd = diferencia / dias;
        const gananciaTotal = pesoActual - primerPeso;

        document.getElementById('pesaje-calc-diferencia').textContent = `${diferencia > 0 ? '+' : ''}${diferencia} kg`;
        document.getElementById('pesaje-calc-gpd').textContent = `${gpd.toFixed(2)} kg/dia`;
        document.getElementById('pesaje-calc-total').textContent = `${gananciaTotal > 0 ? '+' : ''}${gananciaTotal} kg`;
      }

      document.addEventListener('DOMContentLoaded', () => {
        renderKpis();
        renderTabla();
        renderSelectAnimalChart();
        renderSelectAnimalModal();
        renderChartEvolucion(document.getElementById('select-animal-chart').value);
        renderChartCategoria();

        document.getElementById('select-animal-chart').addEventListener('change', (ev) => {
          renderChartEvolucion(ev.target.value);
        });

        document.getElementById('tabla-pesajes-body').addEventListener('click', (ev) => {
          const btn = ev.target.closest('.btn-ver-historial');
          if (btn) abrirHistorial(Number(btn.dataset.id));
        });

        ['f-buscar', 'f-categoria', 'f-potrero', 'f-responsable'].forEach((id) => {
          document.getElementById(id).addEventListener('input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('f-limpiar').addEventListener('click', () => {
          document.getElementById('f-buscar').value = '';
          document.getElementById('f-categoria').value = '';
          document.getElementById('f-potrero').value = '';
          document.getElementById('f-responsable').value = '';
          paginaActual = 1;
          renderTabla();
        });

        document.getElementById('pesaje-fecha').value = '2026-07-15';
        document.getElementById('pesaje-hora').value = new Date().toTimeString().slice(0, 5);
        document.getElementById('pesaje-animal').addEventListener('change', actualizarInfoAnimalModal);
        document.getElementById('pesaje-peso').addEventListener('input', calcularPesaje);
        document.getElementById('pesaje-fecha').addEventListener('change', calcularPesaje);

        document.getElementById('modalRegistrarPesaje').addEventListener('shown.bs.modal', actualizarInfoAnimalModal);

        document.getElementById('btn-guardar-pesaje').addEventListener('click', () => {
          const id = Number(document.getElementById('pesaje-animal').value);
          const animal = ANIMALES_PESAJE.find((item) => item.id === id);
          const peso = document.getElementById('pesaje-peso').value;
          const fecha = document.getElementById('pesaje-fecha').value;
          if (!animal?.id || !peso || !fecha) return;

          const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1];
          const body = new URLSearchParams({ animal_id: animal.id, peso, fecha });
          fetch('/api/pesajes/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf || '' },
            body,
          })
            .then((response) => {
              if (!response.ok) throw new Error('No se pudo guardar el pesaje');
              return response.json();
            })
            .then(() => {
              const [y, m, d] = fecha.split('-');
              const fechaDDMMYYYY = `${d}/${m}/${y}`;
              HISTORIAL[id] = HISTORIAL[id] || [];
              HISTORIAL[id].push({ fecha: fechaDDMMYYYY, peso: Number(peso) });
              reconstruirPesajes();
              renderTabla();
              renderKpis();
              if (Number(document.getElementById('select-animal-chart').value) === id) {
                renderChartEvolucion(id);
              }
              document.getElementById('pesaje-peso').value = '';
              calcularPesaje();
              bootstrap.Modal.getInstance(document.getElementById('modalRegistrarPesaje'))?.hide();
            })
            .catch(() => alert('No se pudo guardar el pesaje. Inténtalo nuevamente.'));
        });
      });
    
