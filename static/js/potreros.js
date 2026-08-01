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
      // Los valores de "actual" coinciden con los usados en el grafico de
      // distribucion por potrero del Dashboard, para que los numeros no
      // se contradigan entre paginas.
      // ------------------------------------------------------------------
      const POTREROS = window.GANASTOCK_DATA?.potreros ?? [
        { nombre: 'Potrero 1', superficie: 45, capacidad: 100, actual: 70, pastura: 'Alfalfa', estado: 'Ocupado', fecha: '12/03/2021', responsable: 'Juan' },
        { nombre: 'Potrero 2', superficie: 38, capacidad: 90, actual: 65, pastura: 'Grama', estado: 'Ocupado', fecha: '03/06/2021', responsable: 'Carlos' },
        { nombre: 'Potrero 3', superficie: 30, capacidad: 80, actual: 60, pastura: 'Sorgo', estado: 'Ocupado', fecha: '20/01/2022', responsable: 'Maria' },
        { nombre: 'Potrero 4', superficie: 42, capacidad: 90, actual: 65, pastura: 'Pastura natural', estado: 'Ocupado', fecha: '08/09/2022', responsable: 'Juan' },
        { nombre: 'Potrero 5', superficie: 25, capacidad: 60, actual: 0, pastura: 'Alfalfa', estado: 'Disponible', fecha: '14/02/2023', responsable: 'Carlos' },
        { nombre: 'Potrero 6', superficie: 20, capacidad: 50, actual: 0, pastura: 'Grama', estado: 'En mantenimiento', fecha: '30/11/2023', responsable: 'Maria' },
      ];

      const ANIMALES_POR_POTRERO = window.GANASTOCK_DATA?.animales_por_potrero ?? {
        'Potrero 1': [
          { caravana: '0231', nombre: 'Luna', categoria: 'Vaca', sexo: 'Hembra', peso: '480 kg' },
          { caravana: '0412', nombre: 'S/N', categoria: 'Ternero', sexo: 'Hembra', peso: '95 kg' },
          { caravana: '0329', nombre: 'S/N', categoria: 'Novillo', sexo: 'Macho', peso: '410 kg' },
        ],
        'Potrero 2': [
          { caravana: '0198', nombre: 'Fierro', categoria: 'Toro', sexo: 'Macho', peso: '720 kg' },
          { caravana: '0305', nombre: 'S/N', categoria: 'Ternero', sexo: 'Macho', peso: '85 kg' },
          { caravana: '0263', nombre: 'Rocio', categoria: 'Vaca', sexo: 'Hembra', peso: '495 kg' },
        ],
        'Potrero 3': [
          { caravana: '0142', nombre: 'Estrella', categoria: 'Vaca', sexo: 'Hembra', peso: '510 kg' },
          { caravana: '0087', nombre: 'S/N', categoria: 'Novillo', sexo: 'Macho', peso: '390 kg' },
        ],
        'Potrero 4': [
          { caravana: '0056', nombre: 'Paloma', categoria: 'Vaquillona', sexo: 'Hembra', peso: '280 kg' },
          { caravana: '0177', nombre: 'Trueno', categoria: 'Toro', sexo: 'Macho', peso: '680 kg' },
        ],
        'Potrero 5': [],
        'Potrero 6': [],
      };

      const ESTADO_BADGE = {
        Disponible: 'text-bg-success',
        Ocupado: 'text-bg-danger',
        'En mantenimiento': 'text-bg-secondary',
      };

      function ocupacionPct(p) {
        return p.capacidad ? Math.round((p.actual / p.capacidad) * 100) : 0;
      }

      function nivelOcupacion(p) {
        if (p.estado === 'En mantenimiento') return 'mantenimiento';
        const pct = ocupacionPct(p);
        if (pct === 0) return 'baja';
        if (pct < 75) return 'media';
        return 'alta';
      }

      let potreroSeleccionado = POTREROS[0].nombre;
      const FILAS_POR_PAGINA = 5;
      let paginaActual = 1;

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const estado = document.getElementById('f-estado').value;
        const pastura = document.getElementById('f-pastura').value;
        const superficie = document.getElementById('f-superficie').value;
        const ocupacion = document.getElementById('f-ocupacion').value;

        return POTREROS.filter((p) => {
          const matchBuscar = !buscar || p.nombre.toLowerCase().includes(buscar);
          const matchSuperficie =
            !superficie ||
            (superficie === 'baja' && p.superficie < 30) ||
            (superficie === 'media' && p.superficie >= 30 && p.superficie <= 40) ||
            (superficie === 'alta' && p.superficie > 40);
          return (
            matchBuscar &&
            matchSuperficie &&
            (!estado || p.estado === estado) &&
            (!pastura || p.pastura === pastura) &&
            (!ocupacion || nivelOcupacion(p) === ocupacion)
          );
        });
      }

      function renderMapa() {
        document.getElementById('mapa-potreros').innerHTML = POTREROS.map((p) => {
          const pct = ocupacionPct(p);
          const nivel = nivelOcupacion(p);
          const seleccionado = p.nombre === potreroSeleccionado ? 'selected' : '';
          return `
          <div class="potrero-block ${nivel} ${seleccionado}" data-nombre="${p.nombre}">
            <h5>${p.nombre}</h5>
            <div class="small">${p.actual} animales</div>
            <div class="small">${p.superficie} ha</div>
            <div class="small fw-semibold">${pct}% ocupacion</div>
          </div>`;
        }).join('');

        document.querySelectorAll('.potrero-block').forEach((block) => {
          block.addEventListener('click', () => {
            potreroSeleccionado = block.dataset.nombre;
            renderMapa();
            renderDetalle();
          });
        });
      }

      function renderTabla() {
        const datos = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

        document.getElementById('tabla-potreros-body').innerHTML = pagina
          .map((p) => {
            const pct = ocupacionPct(p);
            return `
          <tr>
            <td>${p.nombre}</td>
            <td>${p.superficie}</td>
            <td>${p.capacidad}</td>
            <td>${p.actual}</td>
            <td>${pct}%</td>
            <td>${p.pastura}</td>
            <td><span class="badge ${ESTADO_BADGE[p.estado] || 'text-bg-secondary'}">${p.estado}</span></td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary btn-ver-potrero" data-nombre="${p.nombre}" title="Ver detalle"><i class="bi bi-eye"></i></button>
              <button class="btn btn-sm btn-outline-primary" title="Editar"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
            </td>
          </tr>`;
          })
          .join('');

        document.getElementById('tabla-info').textContent = datos.length
          ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} potreros`
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

        document.querySelectorAll('.btn-ver-potrero').forEach((btn) => {
          btn.addEventListener('click', () => {
            potreroSeleccionado = btn.dataset.nombre;
            renderMapa();
            renderDetalle();
          });
        });
      }

      function renderDetalle() {
        const p = POTREROS.find((x) => x.nombre === potreroSeleccionado);
        if (!p) return;

        document.getElementById('detalle-nombre').textContent = p.nombre;

        const animales = ANIMALES_POR_POTRERO[p.nombre] || [];
        document.getElementById('detalle-animales').innerHTML = animales.length
          ? animales
              .map((a) => `<tr><td>#${a.caravana}</td><td>${a.nombre}</td><td>${a.categoria}</td><td>${a.sexo}</td><td>${a.peso}</td></tr>`)
              .join('')
          : `<tr><td colspan="5" class="text-secondary">Sin animales en este potrero.</td></tr>`;
      }

      function actualizarKpis() {
        const total = POTREROS.length;
        const ocupados = POTREROS.filter((p) => p.estado === 'Ocupado').length;
        const libres = POTREROS.filter((p) => p.estado === 'Disponible').length;
        const superficieTotal = POTREROS.reduce((acc, p) => acc + p.superficie, 0);
        const animalesTotal = POTREROS.reduce((acc, p) => acc + p.actual, 0);
        const ocupacionProm = Math.round(POTREROS.reduce((acc, p) => acc + ocupacionPct(p), 0) / total);

        document.getElementById('kpi-total').textContent = total;
        document.getElementById('kpi-ocupados').textContent = ocupados;
        document.getElementById('kpi-libres').textContent = libres;
        document.getElementById('kpi-superficie').textContent = superficieTotal;
        document.getElementById('kpi-animales').textContent = animalesTotal;
        document.getElementById('kpi-ocupacion-promedio').textContent = `${ocupacionProm}%`;
      }

      document.addEventListener('DOMContentLoaded', () => {
        actualizarKpis();
        renderMapa();
        renderTabla();
        renderDetalle();

        ['f-buscar', 'f-estado', 'f-pastura', 'f-superficie', 'f-ocupacion'].forEach((id) => {
          document.getElementById(id).addEventListener('input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('f-limpiar').addEventListener('click', () => {
          ['f-buscar', 'f-estado', 'f-pastura', 'f-superficie', 'f-ocupacion'].forEach((id) => {
            document.getElementById(id).value = '';
          });
          paginaActual = 1;
          renderTabla();
        });

        document.getElementById('form-nuevo-potrero').addEventListener('submit', async (event) => {
          event.preventDefault();
          const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1];
          const response = await fetch('/api/potreros/', {
            method: 'POST', headers: { 'X-CSRFToken': csrf || '' }, body: new FormData(event.currentTarget),
          });
          if (response.ok) window.location.reload();
          else {
            const result = await response.json();
            alert(result.error || 'No se pudo guardar el potrero.');
          }
        });
      });
    
