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

      // ------------------------------------------------------------------
      // Establecimiento
      // ------------------------------------------------------------------
      function getCookie(nombre) {
        return document.cookie.split('; ').find((row) => row.startsWith(nombre + '='))?.split('=')[1] || '';
      }

      function mostrarErrorEstablecimiento(mensaje) {
        const feedback = document.getElementById('est-guardar-error');
        feedback.textContent = mensaje;
        feedback.style.display = 'block';
      }

      document.addEventListener('DOMContentLoaded', () => {
        marcarTemaActivo();

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
    
