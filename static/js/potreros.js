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
      // Datos reales de Django. Si no hay datos cargados, se usa un fallback simple.
      // ------------------------------------------------------------------
      let POTREROS = window.GANASTOCK_DATA?.potreros ?? [
        { nombre: 'Parcela 1', superficie: 0.02, actual: 0, estado: 'En pastoreo', fecha: '', responsable: '-' },
        { nombre: 'Parcela 2', superficie: 0.03, actual: 0, estado: 'En descanso', fecha: '', responsable: '-' },
      ];
      let PARCELA_EDITANDO_ID = null;

      let ANIMALES_POR_POTRERO = window.GANASTOCK_DATA?.animales_por_potrero ?? {
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
        'En pastoreo': 'text-bg-success',
        'En descanso': 'text-bg-warning',
        'En mantenimiento': 'text-bg-danger',
      };

      function nivelEstado(p) {
        const estado = (p.estado || 'En pastoreo').toString().trim();
        if (estado === 'En mantenimiento') return { nivel: 'mantenimiento', color: '#dc3545' };
        if (estado === 'En descanso') return { nivel: 'descanso', color: '#e0a800' };
        return { nivel: 'pastoreo', color: '#198754' };
      }

      let potreroSeleccionado = POTREROS[0]?.nombre || '';
      const FILAS_POR_PAGINA = 5;
      let paginaActual = 1;

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const estado = document.getElementById('f-estado').value;
        return POTREROS.filter((p) => {
          const matchBuscar = !buscar || p.nombre.toLowerCase().includes(buscar);
          return matchBuscar && (!estado || p.estado === estado);
        });
      }

      function renderMapa() {
        document.getElementById('mapa-potreros').innerHTML = POTREROS.map((p) => {
          const estadoInfo = nivelEstado(p);
          const seleccionado = p.nombre === potreroSeleccionado ? 'selected' : '';
          return `
          <div class="potrero-block ${estadoInfo.nivel} ${seleccionado}" data-nombre="${p.nombre}" style="--potrero-color:${estadoInfo.color}">
            <h5>${p.nombre}</h5>
            <div class="small">${p.actual} animales</div>
            <div class="small">${p.superficie} ha</div>
            <div class="small fw-semibold">${p.estado}</div>
          </div>`;
        }).join('');

        document.querySelectorAll('.potrero-block').forEach((block) => {
          block.addEventListener('click', () => {
            potreroSeleccionado = block.dataset.nombre;
            renderMapa();
            renderDetalle();
            document.getElementById('detalle-parcela').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
            return `
          <tr>
            <td>${p.nombre}</td>
            <td>${p.actual}</td>
            <td><span class="badge ${ESTADO_BADGE[p.estado] || 'text-bg-secondary'}">${p.estado}</span></td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary btn-ver-potrero" data-id="${p.id}" data-nombre="${p.nombre}" title="Ver detalle"><i class="bi bi-eye"></i></button>
              <button class="btn btn-sm btn-outline-primary btn-editar-potrero" data-id="${p.id}" data-nombre="${p.nombre}" title="Editar parcela"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-danger btn-eliminar-potrero" data-id="${p.id}" data-nombre="${p.nombre}" title="Eliminar parcela"><i class="bi bi-trash"></i></button>
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

        document.querySelectorAll('.btn-editar-potrero').forEach((btn) => {
          btn.addEventListener('click', () => {
            const parcela = POTREROS.find((p) => String(p.id) === String(btn.dataset.id));
            if (!parcela) return;
            abrirModalEdicion(parcela);
          });
        });

        document.querySelectorAll('.btn-eliminar-potrero').forEach((btn) => {
          btn.addEventListener('click', async () => {
            const parcela = POTREROS.find((p) => String(p.id) === String(btn.dataset.id));
            if (!parcela || !window.confirm(`¿Eliminar definitivamente ${parcela.nombre}?`)) return;
            const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1];
            const response = await fetch(`/api/potreros/${parcela.id}/eliminar/`, {
              method: 'POST', headers: { 'X-CSRFToken': csrf || '' },
            });
            if (!response.ok) {
              alert('No se pudo eliminar la parcela.');
              return;
            }
            POTREROS = POTREROS.filter((p) => String(p.id) !== String(parcela.id));
            delete ANIMALES_POR_POTRERO[parcela.nombre];
            if (potreroSeleccionado === parcela.nombre) {
              potreroSeleccionado = POTREROS[0]?.nombre || '';
            }
            actualizarKpis();
            renderMapa();
            renderTabla();
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

      function abrirModalEdicion(parcela) {
        const modal = document.getElementById('modalNuevoPotrero');
        const title = document.getElementById('modalNuevoPotreroTitle');
        const form = document.getElementById('form-nuevo-potrero');
        document.getElementById('form-potrero-id').value = parcela.id || '';
        form.querySelector('[name="descripcion"]').value = parcela.descripcion || parcela.nombre || '';
        form.querySelector('[name="ancho"]').value = parcela.ancho ?? '';
        form.querySelector('[name="largo"]').value = parcela.largo ?? '';
        form.querySelector('[name="estado"]').value = parcela.estado || 'En pastoreo';
        form.querySelector('[name="observaciones"]').value = '';
        title.textContent = 'Editar Parcela';
        PARCELA_EDITANDO_ID = parcela.id;
        bootstrap.Modal.getOrCreateInstance(modal).show();
      }

      function resetearFormulario() {
        const form = document.getElementById('form-nuevo-potrero');
        form.reset();
        document.getElementById('form-potrero-id').value = '';
        document.getElementById('modalNuevoPotreroTitle').textContent = 'Nueva Parcela';
        PARCELA_EDITANDO_ID = null;
      }

      function actualizarKpis() {
        const total = POTREROS.length;
        const ocupados = POTREROS.filter((p) => p.actual > 0).length;
        const libres = total - ocupados;
        const animalesTotal = POTREROS.reduce((acc, p) => acc + p.actual, 0);

        document.getElementById('kpi-total').textContent = total;
        document.getElementById('kpi-ocupados').textContent = ocupados;
        document.getElementById('kpi-libres').textContent = libres;
        document.getElementById('kpi-animales').textContent = animalesTotal;
        document.getElementById('kpi-ocupacion-promedio').textContent = '—';
      }

      document.addEventListener('DOMContentLoaded', () => {
        actualizarKpis();
        renderMapa();
        renderTabla();
        renderDetalle();

        ['f-buscar', 'f-estado'].forEach((id) => {
          document.getElementById(id).addEventListener('input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('f-limpiar').addEventListener('click', () => {
          ['f-buscar', 'f-estado'].forEach((id) => {
            document.getElementById(id).value = '';
          });
          paginaActual = 1;
          renderTabla();
        });

        const formNuevoPotrero = document.getElementById('form-nuevo-potrero');
        const btnGuardarPotrero = document.getElementById('btn-guardar-potrero');

        document.addEventListener('click', (event) => {
          const target = event.target;
          if (target instanceof HTMLElement && target.id === 'btn-guardar-potrero') {
            event.preventDefault();
            event.stopPropagation();
            if (formNuevoPotrero) {
              if (typeof formNuevoPotrero.requestSubmit === 'function') {
                formNuevoPotrero.requestSubmit();
              } else {
                formNuevoPotrero.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
              }
            }
          }
        });

        formNuevoPotrero?.addEventListener('submit', async (event) => {
          event.preventDefault();
          const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1];
          const formData = new FormData(event.currentTarget);
          const response = await fetch('/api/potreros/', {
            method: 'POST', headers: { 'X-CSRFToken': csrf || '' }, body: formData,
          });
          if (response.ok) {
            const result = await response.json();
            const parcela = result.parcela || {
              id: result.id,
              nombre: (formData.get('descripcion') || '').toString().trim() || 'Parcela nueva',
              ancho: Number(formData.get('ancho')) || 0,
              largo: Number(formData.get('largo')) || 0,
              superficie: ((Number(formData.get('ancho')) || 0) * (Number(formData.get('largo')) || 0)) / 10000,
              actual: 0,
              estado: (formData.get('estado') || 'En pastoreo').toString().trim(),
              fecha: '',
              responsable: '-',
              descripcion: (formData.get('observaciones') || '').toString().trim(),
            };
            if (PARCELA_EDITANDO_ID) {
              POTREROS = POTREROS.map((p) => (String(p.id) === String(parcela.id) ? { ...p, ...parcela } : p));
            } else {
              POTREROS = [{ ...parcela, actual: 0, fecha: '', responsable: '-' }, ...POTREROS];
            }
            ANIMALES_POR_POTRERO[parcela.nombre] = ANIMALES_POR_POTRERO[parcela.nombre] || [];
            window.GANASTOCK_DATA = window.GANASTOCK_DATA || {};
            window.GANASTOCK_DATA.potreros = POTREROS;
            potreroSeleccionado = parcela.nombre;
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNuevoPotrero')).hide();
            resetearFormulario();
            actualizarKpis();
            renderMapa();
            renderTabla();
            renderDetalle();
            setTimeout(() => {
              actualizarKpis();
              renderMapa();
              renderTabla();
              renderDetalle();
            }, 0);
          } else {
            const result = await response.json();
            alert(result.error || 'No se pudo guardar el potrero.');
          }
        });

        document.querySelector('[data-bs-target="#modalNuevoPotrero"]').addEventListener('click', () => {
          resetearFormulario();
        });

        document.getElementById('modalNuevoPotrero').addEventListener('hidden.bs.modal', () => {
          resetearFormulario();
        });
      });
    
