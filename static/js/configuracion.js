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
        globalThis.vacappSetTheme = setStoredTheme;
        globalThis.vacappApplyTheme = setTheme;
        globalThis.vacappGetTheme = getPreferredTheme;
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
              if (typeof marcarTemaActivo === 'function') marcarTemaActivo();
            });
          });
        });
      })();
    

      // ------------------------------------------------------------------
      // MOCK DATA: reemplazar por datos reales cuando se conecte con Django.
      // ------------------------------------------------------------------
      let CATEGORIAS = ['Toro', 'Vaca', 'Novillo', 'Vaquillona', 'Ternero'];
      let RAZAS = ['Angus', 'Brangus', 'Hereford', 'Braford', 'Brahman', 'Criolla'];
      let PASTURAS = ['Pastura natural', 'Pastura implantada', 'Verdeo de invierno', 'Verdeo de verano', 'Rastrojo'];

      let VACUNAS = [
        { nombre: 'Aftosa', laboratorio: 'Biogenesis Bago', tipo: 'Viral', dosis: '2 ml', frecuencia: 'Semestral' },
        { nombre: 'Brucelosis', laboratorio: 'Vetanco', tipo: 'Bacteriana', dosis: '2 ml', frecuencia: 'Unica (3 a 8 meses)' },
        { nombre: 'Carbunclo', laboratorio: 'Biogenesis Bago', tipo: 'Bacteriana', dosis: '1 ml', frecuencia: 'Anual' },
        { nombre: 'Clostridiosis', laboratorio: 'Vetanco', tipo: 'Bacteriana', dosis: '5 ml', frecuencia: 'Anual' },
        { nombre: 'Rabia', laboratorio: 'MSD Salud Animal', tipo: 'Viral', dosis: '2 ml', frecuencia: 'Anual' },
      ];

      let ESTADOS_POTRERO = [
        { nombre: 'Disponible', color: '#198754' },
        { nombre: 'En descanso', color: '#ffc107' },
        { nombre: 'Ocupado', color: '#0d6efd' },
        { nombre: 'En recuperacion', color: '#dc3545' },
      ];

      // ------------------------------------------------------------------
      // Listas simples (Categorias, Razas, Tipos de pastura): comparten
      // un unico modal generico para agregar/editar.
      // ------------------------------------------------------------------
      const LISTAS_SIMPLES = {
        categoria: { getArr: () => CATEGORIAS, tbody: 'tabla-categorias', label: 'categoria' },
        raza: { getArr: () => RAZAS, tbody: 'tabla-razas', label: 'raza' },
        pastura: { getArr: () => PASTURAS, tbody: 'tabla-pasturas', label: 'tipo de pastura' },
      };
      let listaSimpleContexto = { tipo: null, index: null };

      function renderListaSimple(tipo) {
        const { getArr, tbody } = LISTAS_SIMPLES[tipo];
        document.getElementById(tbody).innerHTML = getArr()
          .map(
            (nombre, i) => `
          <tr>
            <td>${nombre}</td>
            <td class="text-end">
              <button type="button" class="btn btn-sm btn-outline-secondary" onclick="abrirModalListaSimple('${tipo}', ${i})" title="Editar">
                <i class="bi bi-pencil-square"></i>
              </button>
              <button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarListaSimple('${tipo}', ${i})" title="Eliminar">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>`,
          )
          .join('');
      }

      function abrirModalListaSimple(tipo, index = null) {
        listaSimpleContexto = { tipo, index };
        const { getArr, label } = LISTAS_SIMPLES[tipo];
        document.getElementById('ls-modal-titulo').textContent = index === null ? `Nueva ${label}` : `Editar ${label}`;
        document.getElementById('ls-modal-input').value = index === null ? '' : getArr()[index];
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalListaSimple')).show();
      }

      function guardarListaSimple() {
        const valor = document.getElementById('ls-modal-input').value.trim();
        if (!valor) return;
        const { tipo, index } = listaSimpleContexto;
        const arr = LISTAS_SIMPLES[tipo].getArr();
        if (index === null) arr.push(valor);
        else arr[index] = valor;
        renderListaSimple(tipo);
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalListaSimple')).hide();
      }

      function eliminarListaSimple(tipo, index) {
        const { getArr, label } = LISTAS_SIMPLES[tipo];
        const nombre = getArr()[index];
        confirmarAccion('Eliminar ' + label, `¿Seguro que deseas eliminar "${nombre}"? Esta accion no se puede deshacer.`, () => {
          getArr().splice(index, 1);
          renderListaSimple(tipo);
        });
      }

      // ------------------------------------------------------------------
      // Vacunas
      // ------------------------------------------------------------------
      let vacunaEditIndex = null;

      function renderVacunas() {
        document.getElementById('tabla-vacunas').innerHTML = VACUNAS.map(
          (v, i) => `
          <tr>
            <td>${v.nombre}</td>
            <td>${v.laboratorio}</td>
            <td>${v.tipo}</td>
            <td>${v.dosis}</td>
            <td>${v.frecuencia}</td>
            <td class="text-end">
              <button type="button" class="btn btn-sm btn-outline-secondary" onclick="abrirModalVacuna(${i})" title="Editar">
                <i class="bi bi-pencil-square"></i>
              </button>
              <button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarVacuna(${i})" title="Eliminar">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>`,
        ).join('');
      }

      function abrirModalVacuna(index = null) {
        vacunaEditIndex = index;
        const v = index === null ? { nombre: '', laboratorio: '', tipo: 'Viral', dosis: '', frecuencia: '' } : VACUNAS[index];
        document.getElementById('vac-modal-titulo').textContent = index === null ? 'Nueva vacuna' : 'Editar vacuna';
        document.getElementById('vac-nombre').value = v.nombre;
        document.getElementById('vac-laboratorio').value = v.laboratorio;
        document.getElementById('vac-tipo').value = v.tipo;
        document.getElementById('vac-dosis').value = v.dosis;
        document.getElementById('vac-frecuencia').value = v.frecuencia;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalVacuna')).show();
      }

      function guardarVacuna() {
        const nueva = {
          nombre: document.getElementById('vac-nombre').value.trim(),
          laboratorio: document.getElementById('vac-laboratorio').value.trim(),
          tipo: document.getElementById('vac-tipo').value,
          dosis: document.getElementById('vac-dosis').value.trim(),
          frecuencia: document.getElementById('vac-frecuencia').value.trim(),
        };
        if (!nueva.nombre) return;
        if (vacunaEditIndex === null) VACUNAS.push(nueva);
        else VACUNAS[vacunaEditIndex] = nueva;
        renderVacunas();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalVacuna')).hide();
      }

      function eliminarVacuna(index) {
        const nombre = VACUNAS[index].nombre;
        confirmarAccion('Eliminar vacuna', `¿Seguro que deseas eliminar "${nombre}" del listado de vacunas?`, () => {
          VACUNAS.splice(index, 1);
          renderVacunas();
        });
      }

      // ------------------------------------------------------------------
      // Estados del potrero
      // ------------------------------------------------------------------
      let estadoEditIndex = null;

      function renderEstadosPotrero() {
        document.getElementById('tabla-estados-potrero').innerHTML = ESTADOS_POTRERO.map(
          (e, i) => `
          <tr>
            <td><span class="d-inline-block rounded-circle" style="width:18px;height:18px;background:${e.color}"></span></td>
            <td>${e.nombre}</td>
            <td class="text-end">
              <button type="button" class="btn btn-sm btn-outline-secondary" onclick="abrirModalEstadoPotrero(${i})" title="Editar">
                <i class="bi bi-pencil-square"></i>
              </button>
              <button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarEstadoPotrero(${i})" title="Eliminar">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>`,
        ).join('');
      }

      function abrirModalEstadoPotrero(index = null) {
        estadoEditIndex = index;
        const e = index === null ? { nombre: '', color: '#0d6efd' } : ESTADOS_POTRERO[index];
        document.getElementById('est-modal-titulo').textContent = index === null ? 'Nuevo estado' : 'Editar estado';
        document.getElementById('est-nombre').value = e.nombre;
        document.getElementById('est-color').value = e.color;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalEstadoPotrero')).show();
      }

      function guardarEstadoPotrero() {
        const nombre = document.getElementById('est-nombre').value.trim();
        const color = document.getElementById('est-color').value;
        if (!nombre) return;
        if (estadoEditIndex === null) ESTADOS_POTRERO.push({ nombre, color });
        else ESTADOS_POTRERO[estadoEditIndex] = { nombre, color };
        renderEstadosPotrero();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalEstadoPotrero')).hide();
      }

      function eliminarEstadoPotrero(index) {
        const nombre = ESTADOS_POTRERO[index].nombre;
        confirmarAccion('Eliminar estado', `¿Seguro que deseas eliminar el estado "${nombre}"?`, () => {
          ESTADOS_POTRERO.splice(index, 1);
          renderEstadosPotrero();
        });
      }

      // ------------------------------------------------------------------
      // Modal de confirmacion generico (para toda accion critica/destructiva)
      // ------------------------------------------------------------------
      let confirmarCallback = null;

      function confirmarAccion(titulo, mensaje, onConfirm) {
        document.getElementById('confirmar-titulo').textContent = titulo;
        document.getElementById('confirmar-mensaje').textContent = mensaje;
        confirmarCallback = onConfirm;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalConfirmar')).show();
      }

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
      // Apariencia
      // ------------------------------------------------------------------
      function marcarTemaActivo() {
        const actual = globalThis.vacappGetTheme ? globalThis.vacappGetTheme() : 'light';
        document.getElementById('tema-opcion-light').classList.toggle('active', actual === 'light');
        document.getElementById('tema-opcion-dark').classList.toggle('active', actual === 'dark');
      }

      function elegirTema(tema) {
        if (globalThis.vacappSetTheme) globalThis.vacappSetTheme(tema);
        if (globalThis.vacappApplyTheme) globalThis.vacappApplyTheme(tema);
        marcarTemaActivo();
      }

      function elegirColor(el) {
        document.querySelectorAll('.vacapp-color-swatch').forEach((s) => s.classList.remove('active'));
        el.classList.add('active');
        const color = el.dataset.color;
        document.getElementById('preview-btn').style.background = color;
        document.getElementById('preview-badge').style.background = color;
      }

      document.addEventListener('DOMContentLoaded', () => {
        renderListaSimple('categoria');
        renderListaSimple('raza');
        renderListaSimple('pastura');
        renderVacunas();
        renderEstadosPotrero();
        marcarTemaActivo();

        document.getElementById('confirmar-btn-aceptar').addEventListener('click', () => {
          if (typeof confirmarCallback === 'function') confirmarCallback();
          bootstrap.Modal.getOrCreateInstance(document.getElementById('modalConfirmar')).hide();
        });

        // Vista previa de logo
        document.getElementById('empresa-logo-input').addEventListener('change', (e) => {
          const file = e.target.files[0];
          if (!file) return;
          const reader = new FileReader();
          reader.onload = (ev) => {
            document.getElementById('empresa-logo-preview').innerHTML = `<img src="${ev.target.result}" alt="Logo" />`;
          };
          reader.readAsDataURL(file);
        });

        // Formularios "Guardar cambios" (mock, sin backend todavia)
        ['form-empresa', 'form-establecimiento'].forEach((id) => {
          document.getElementById(id).addEventListener('submit', (e) => {
            e.preventDefault();
            mostrarExito(e.target.querySelector('button[type="submit"]'), 'Cambios guardados');
          });
        });

        document.getElementById('btn-guardar-seguridad').addEventListener('click', function () {
          mostrarExito(this.id, 'Preferencias guardadas');
        });

        document.getElementById('btn-crear-respaldo').addEventListener('click', function () {
          mostrarExito(this.id, 'Respaldo creado');
        });

        // Cambio de contraseña: validacion simple
        const nueva = document.getElementById('seg-nueva-pass');
        const confirmar = document.getElementById('seg-confirmar-pass');
        document.getElementById('form-password').addEventListener('submit', (e) => {
          e.preventDefault();
          if (nueva.value !== confirmar.value) {
            confirmar.classList.add('is-invalid');
            return;
          }
          confirmar.classList.remove('is-invalid');
          mostrarExito(e.target.querySelector('button[type="submit"]'), 'Contraseña actualizada');
          e.target.reset();
        });
        confirmar.addEventListener('input', () => confirmar.classList.remove('is-invalid'));
      });
    
