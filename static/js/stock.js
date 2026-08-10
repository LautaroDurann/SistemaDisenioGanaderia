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
      const ANIMALES = window.HUACAPP_DATA?.animales ?? [
        { caravana: '0231', nombre: 'Luna', categoria: 'Vaca', sexo: 'Hembra', raza: 'Angus', edad: '4 años', peso: '480 kg', potrero: 'Potrero 1', estado: 'Activo', ingreso: '10/07/2026', notas: 'Buena productora, sin antecedentes de pérdida de peso. Apta para servicio.' },
        { caravana: '0198', nombre: 'Fierro', categoria: 'Toro', sexo: 'Macho', raza: 'Braford', edad: '5 años', peso: '720 kg', potrero: 'Potrero 2', estado: 'Vendido', ingreso: '02/02/2024', notas: 'Reproductor principal del establecimiento hasta su venta en el remate local.' },
        { caravana: '0305', nombre: 'S/N', categoria: 'Ternero', sexo: 'Macho', raza: 'Angus', edad: '2 meses', peso: '85 kg', potrero: 'Potrero 2', estado: 'Activo', ingreso: '05/07/2026', notas: 'Nacido en el potrero, todavía sin identificación definitiva de nombre.' },
        { caravana: '0142', nombre: 'Estrella', categoria: 'Vaca', sexo: 'Hembra', raza: 'Hereford', edad: '6 años', peso: '510 kg', potrero: 'Potrero 3', estado: 'Muerto', ingreso: '15/03/2021', notas: 'Baja por causas naturales. Se mantiene el registro histórico completo.' },
        { caravana: '0087', nombre: 'S/N', categoria: 'Novillo', sexo: 'Macho', raza: 'Braford', edad: '2 años', peso: '390 kg', potrero: 'Potrero 3', estado: 'Activo', ingreso: '29/06/2026', notas: 'Ganancia de peso por debajo de lo esperado para la categoría, en seguimiento.' },
        { caravana: '0056', nombre: 'Paloma', categoria: 'Vaquillona', sexo: 'Hembra', raza: 'Angus', edad: '1 año', peso: '280 kg', potrero: 'Potrero 4', estado: 'Activo', ingreso: '18/01/2026', notas: 'Buena candidata a servicio en la próxima temporada.' },
        { caravana: '0412', nombre: 'S/N', categoria: 'Ternero', sexo: 'Hembra', raza: 'Hereford', edad: '3 meses', peso: '95 kg', potrero: 'Potrero 1', estado: 'Activo', ingreso: '20/04/2026', notas: 'Excelente desarrollo, mejor ganancia diaria del lote de terneros.' },
        { caravana: '0177', nombre: 'Trueno', categoria: 'Toro', sexo: 'Macho', raza: 'Angus', edad: '3 años', peso: '680 kg', potrero: 'Potrero 4', estado: 'Activo', ingreso: '11/09/2023', notas: 'Reproductor de respaldo, sin observaciones sanitarias.' },
        { caravana: '0263', nombre: 'Rocío', categoria: 'Vaca', sexo: 'Hembra', raza: 'Braford', edad: '5 años', peso: '495 kg', potrero: 'Potrero 2', estado: 'Activo', ingreso: '07/06/2021', notas: 'Pendiente de próximo control de peso.' },
        { caravana: '0329', nombre: 'S/N', categoria: 'Novillo', sexo: 'Macho', raza: 'Hereford', edad: '2 años', peso: '410 kg', potrero: 'Potrero 1', estado: 'Vendido', ingreso: '02/02/2024', notas: 'Vendido por baja administrativa junto con el lote de novillos.' },
      ];
      ANIMALES.forEach((animal) => {
        animal.parcela ??= animal.potrero ?? 'Sin asignar';
        animal.tipo_animal ??= 'Bovino';
      });

      const ESTADO_BADGE = {
        Activo: 'text-bg-success',
        Vendido: 'text-bg-primary',
        Muerto: 'text-bg-danger',
      };

      const FILAS_POR_PAGINA = 10;
      let paginaActual = 1;
      let animalSeleccionadoId = null;
      let animalEnEdicion = null;

      function aplicarFiltros() {
        const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
        const tipoAnimal = document.getElementById('f-tipo-animal').value;
        const categoria = document.getElementById('f-categoria').value;
        const sexo = document.getElementById('f-sexo').value;
        const estado = document.getElementById('f-estado').value;
        const parcela = document.getElementById('f-parcela').value;

        return ANIMALES.filter((a) => {
          const matchBuscar =
            !buscar ||
            a.caravana.toLowerCase().includes(buscar) ||
            a.nombre.toLowerCase().includes(buscar);
          return (
            matchBuscar &&
            (!tipoAnimal || a.tipo_animal === tipoAnimal) &&
            (!categoria || a.categoria === categoria) &&
            (!sexo || a.sexo === sexo) &&
            (!estado || a.estado === estado) &&
            (!parcela || a.parcela === parcela)
          );
        });
      }

      function renderTabla() {
        const datos = aplicarFiltros();
        const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
        if (paginaActual > totalPaginas) paginaActual = totalPaginas;

        const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
        const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

        const tbody = document.getElementById('tabla-stock-body');
        tbody.innerHTML = pagina
          .map(
            (a) => `
          <tr data-id="${a.id}" class="${a.id === animalSeleccionadoId ? 'table-active' : ''}">
            <td>#${a.caravana}</td>
            <td>${a.nombre}</td>
            <td>${a.tipo_animal}</td>
            <td>${a.sexo}</td>
            <td><span class="badge ${a.castrado ? 'text-bg-success' : 'text-bg-secondary'}">${a.castrado ? 'Sí' : 'No'}</span></td>
            <td>${a.raza}</td>
            <td>${a.edad}</td>
            <td>${a.peso}</td>
            <td>${a.parcela}</td>
            <td><span class="badge ${ESTADO_BADGE[a.estado] || 'text-bg-secondary'}">${a.estado}</span></td>
            <td>${a.ingreso}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-primary btn-editar-animal" data-id="${a.id}" title="Editar"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-sm btn-outline-danger btn-eliminar-animal" data-id="${a.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
            </td>
          </tr>`,
          )
          .join('');

        document.getElementById('tabla-info').textContent = datos.length
          ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} animales`
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

        actualizarKpis(datos);
      }

      function actualizarKpis(datos) {
        document.getElementById('kpi-total').textContent = ANIMALES.length;
        document.getElementById('kpi-bovinos').textContent = ANIMALES.filter((a) => a.tipo_animal === 'Bovino').length;
        document.getElementById('kpi-ovinos').textContent = ANIMALES.filter((a) => a.tipo_animal === 'Ovino').length;
        document.getElementById('kpi-porcinos').textContent = ANIMALES.filter((a) => a.tipo_animal === 'Porcino').length;
      }

      // ------------------------------------------------------------------
      // Ficha del animal (panel lateral, a la derecha de la tabla). Al conectar
      // el backend, reemplazar por un fetch real a la API usando el id del animal.
      // ------------------------------------------------------------------
      const COLOR_CATEGORIA = {
        Toro: '#212529',
        Vaca: '#0d6efd',
        Novillo: '#6c757d',
        Vaquillona: '#0dcaf0',
        Ternero: '#198754',
      };

      function renderFichaAnimal(id) {
        const a = ANIMALES.find((x) => x.id === id);
        if (!a) return;
        animalSeleccionadoId = a.id;

        const imagen = document.getElementById("ficha-imagen");
       
        

        document.getElementById('ficha-nombre').textContent = a.nombre === 'S/N' ? `Sin nombre (#${a.caravana})` : a.nombre;
        document.getElementById('ficha-caravana').textContent = `Caravana #${a.caravana}`;
        document.getElementById('ficha-categoria').textContent = a.categoria;
        document.getElementById('ficha-sexo').textContent = a.sexo;
        document.getElementById('ficha-raza').textContent = a.raza;
        document.getElementById('ficha-edad').textContent = a.edad;
        document.getElementById('ficha-peso').textContent = a.peso;
        document.getElementById('ficha-potrero').textContent = a.parcela;
        document.getElementById('ficha-establecimiento').textContent = a.establecimiento || '-';
        document.getElementById('ficha-categoria').closest('li').classList.toggle('d-none', a.tipo_animal !== 'Bovino');
        const fichaFoto = document.getElementById('ficha-foto');
        if (a.foto_url) {
          fichaFoto.innerHTML = `<img src="${a.foto_url}" alt="Foto de ${a.nombre || 'animal'}" style="width: 100%; height: 100%; object-fit: contain;">`;
        } else {
          fichaFoto.innerHTML = `
            <div class="placeholder-foto" id="ficha-foto-placeholder">
              <i class="bi bi-image fs-1"></i>
              <span>Sin imagen</span>
            </div>`;
        }
        document.getElementById('ficha-estado').innerHTML = `<span class="badge ${ESTADO_BADGE[a.estado] || 'text-bg-secondary'}">${a.estado}</span>`;
        document.getElementById('ficha-ingreso').textContent = a.ingreso;
        document.getElementById('ficha-notas').textContent = a.notas || 'Sin notas cargadas.';
        document.getElementById('ficha-tipo').textContent = a.tipo_animal;
        document.getElementById('ficha-pesos-iniciales').textContent = `${a.peso_al_nacer || '-'} / ${a.peso_al_destete || '-'} kg`;
        document.getElementById('ficha-dieta').textContent = a.dieta;
        document.getElementById('ficha-progenitores').textContent = `${a.madre} / ${a.padre}`;
        document.getElementById('ficha-condicion').textContent = [a.vivo ? 'Vivo' : 'Muerto', a.vendido ? 'Vendido' : 'No vendido', a.enfermo ? 'Enfermo' : 'Sano'].join(' · ');
        document.getElementById('ficha-castrado').textContent = a.castrado ? 'Sí' : 'No';
        document.getElementById('ficha-color').textContent = a.color || '-';
        document.getElementById('ficha-valores').textContent = `$${a.costo_adquisicion || '-'} / $${a.precio_venta || '-'}`;
        document.getElementById('ficha-operaciones').textContent = `${a.compra} / ${a.venta}`;
        document.getElementById('ficha-diametro').textContent = a.diametro_escrotal ? `${a.diametro_escrotal} cm` : '-';
        document.getElementById('fila-ficha-diametro').classList.toggle('d-none', a.sexo !== 'Macho');
      }

      function cargarAnimalEnFormulario(animal) {
        animalEnEdicion = animal;
        document.getElementById('modalNuevoAnimalTitulo').innerHTML = '<i class="bi bi-pencil me-2"></i>Editar animal';
        document.getElementById('animal-caravana').value = animal.caravana;
        document.getElementById('animal-nombre').value = animal.nombre;
        document.getElementById('animal-sexo').value = animal.sexo;
        document.getElementById('animal-tipo').value = animal.tipo_animal;
        document.getElementById('animal-raza').value = animal.raza === '-' ? '' : animal.raza;
        document.getElementById('animal-peso').value = animal.peso_actual_valor;
        document.getElementById('animal-fecha-nacimiento').value = animal.ingreso === '-' ? '' : animal.ingreso;
        const selectEstablecimiento = document.getElementById('animal-establecimiento');
        selectEstablecimiento.value = animal.establecimiento_id || '';
        cargarParcelasDeEstablecimiento(selectEstablecimiento.value);
        document.getElementById('animal-parcela').value = animal.parcela_id || '';
        document.getElementById('animal-peso-nacer').value = animal.peso_al_nacer;
        document.getElementById('animal-peso-destete').value = animal.peso_al_destete;
        document.getElementById('animal-diametro').value = animal.diametro_escrotal;
        document.getElementById('animal-color').value = animal.color;
        document.getElementById('animal-dieta').value = animal.dieta_id || '';
        document.getElementById('animal-madre').value = animal.madre_id || '';
        document.getElementById('animal-padre').value = animal.padre_id || '';
        const tieneCompra = Boolean(animal.compra_id) && animal.compra && animal.compra !== 'Sin compra asociada';
        document.getElementById('grupo-compra').classList.toggle('d-none', !tieneCompra);
        document.getElementById('grupo-costo').classList.toggle('d-none', !tieneCompra);
        if (tieneCompra) {
          document.getElementById('animal-compra').value = animal.compra;
          document.getElementById('animal-costo').value = animal.costo_adquisicion || '-';
        }
        const tieneVenta = Boolean(animal.venta_id) && animal.venta && animal.venta !== 'Sin venta asociada';
        document.getElementById('grupo-venta').classList.toggle('d-none', !tieneVenta);
        document.getElementById('grupo-precio-venta').classList.toggle('d-none', !tieneVenta);
        if (tieneVenta) {
          document.getElementById('animal-venta').value = animal.venta;
          document.getElementById('animal-precio-venta').value = animal.precio_venta || '-';
        }
        document.getElementById('animal-vendido').checked = animal.vendido;
        document.getElementById('animal-vivo').checked = animal.vivo;
        document.getElementById('animal-enfermo').checked = animal.enfermo;
        document.getElementById('animal-castrado').checked = animal.castrado;
        actualizarCampoDiametro();
        document.getElementById('animal-descripcion').value = animal.notas === '-' ? '' : animal.notas;
        const preview = document.getElementById('foto-preview');
        document.getElementById('animal-foto').value = '';
        document.getElementById('animal-eliminar-foto').value = '';
        document.getElementById('foto-acciones').classList.toggle('d-none', !animal.foto_url);
        if (animal.foto_url) {
          preview.innerHTML = `<img src="${animal.foto_url}" alt="Foto actual" class="img-fluid rounded" style="max-height: 180px; width: 100%; object-fit: contain;">`;
          preview.classList.remove('d-none');
        } else {
          preview.innerHTML = '<div class="text-muted small">Sin imagen cargada</div>';
          preview.classList.remove('d-none');
        }
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNuevoAnimal')).show();
      }

      // ------------------------------------------------------------------
      // Hace que la fila "Tabla + Ficha del animal" ocupe toda la altura
      // restante de la pantalla (entre el encabezado y el footer), en vez
      // de quedar con su alto natural de contenido.
      // ------------------------------------------------------------------
      function ajustarAlturaFilaCompleta() {
        const fila = document.getElementById('fila-tabla-ficha');
        if (!fila) return;
        const footer = document.querySelector('.app-footer');
        const top = fila.getBoundingClientRect().top;
        const footerHeight = footer ? footer.getBoundingClientRect().height : 0;
        const margenInferior = 24;
        const disponible = window.innerHeight - top - footerHeight - margenInferior;
        fila.style.minHeight = Math.max(disponible, 420) + 'px';
      }

      function actualizarCampoDiametro() {
        const esMacho = document.getElementById('animal-sexo').value === 'Macho';
        document.getElementById('grupo-diametro-escrotal').classList.toggle('d-none', !esMacho);
        if (!esMacho) document.getElementById('animal-diametro').value = '';
      }

      function agregarOpciones(selectId, datos, texto, filtro = () => true) {
        const select = document.getElementById(selectId);
        datos.filter(filtro).forEach((dato) => select.add(new Option(texto(dato), dato.id)));
      }

      function cargarParcelasDeEstablecimiento(establecimientoId) {
        const selectParcela = document.getElementById('animal-parcela');
        selectParcela.innerHTML = '<option value="">Sin asignar</option>';
        if (!establecimientoId) return;
        (window.HUACAPP_DATA?.parcelas || [])
          .filter((parcela) => parcela.establecimiento_id === establecimientoId)
          .forEach((parcela) => selectParcela.add(new Option(parcela.nombre, parcela.id)));
      }

      document.addEventListener('DOMContentLoaded', () => {
        if (ANIMALES.length) renderFichaAnimal(ANIMALES[0].caravana);
        renderTabla();
        ajustarAlturaFilaCompleta();

        let resizeTimeout;
        window.addEventListener('resize', () => {
          clearTimeout(resizeTimeout);
          resizeTimeout = setTimeout(ajustarAlturaFilaCompleta, 150);
        });

        document.getElementById('tabla-stock-body').addEventListener('click', (ev) => {
          const botonEditar = ev.target.closest('.btn-editar-animal');
          if (botonEditar) {
            ev.stopPropagation();
            const animal = ANIMALES.find((item) => item.id === Number(botonEditar.dataset.id));
            if (animal) cargarAnimalEnFormulario(animal);
            return;
          }
          const botonEliminar = ev.target.closest('.btn-eliminar-animal');
          if (botonEliminar) {
            ev.stopPropagation();
            const animal = ANIMALES.find((item) => item.id === Number(botonEliminar.dataset.id));
            if (!animal || !window.confirm(`¿Eliminar definitivamente a #${animal.caravana} ${animal.nombre}?`)) return;
            const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1];
            fetch(`/api/animales/${animal.id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf || '' } })
              .then((response) => {
                if (!response.ok) throw new Error();
                const index = ANIMALES.findIndex((item) => item.id === animal.id);
                if (index !== -1) ANIMALES.splice(index, 1);
                if (animalSeleccionadoId === animal.id) {
                  animalSeleccionadoId = null;
                  if (ANIMALES.length) renderFichaAnimal(ANIMALES[0].id);
                }
                renderTabla();
              })
              .catch(() => alert('No se pudo eliminar el animal.'));
            return;
          }
          const fila = ev.target.closest('tr[data-id]');
          if (fila) {
            renderFichaAnimal(Number(fila.dataset.id));
            renderTabla();
          }
        });

        ['f-buscar', 'f-tipo-animal', 'f-categoria', 'f-sexo', 'f-estado', 'f-parcela'].forEach((id) => {
          document.getElementById(id).addEventListener('input', () => {
            paginaActual = 1;
            renderTabla();
          });
        });

        document.getElementById('f-limpiar').addEventListener('click', () => {
          document.getElementById('f-buscar').value = '';
          document.getElementById('f-tipo-animal').value = '';
          document.getElementById('f-categoria').value = '';
          document.getElementById('f-sexo').value = '';
          document.getElementById('f-estado').value = '';
          document.getElementById('f-parcela').value = '';
          document.getElementById('grupo-f-categoria').classList.add('d-none');
          paginaActual = 1;
          renderTabla();
        });

        document.getElementById('f-tipo-animal').addEventListener('change', (event) => {
          const esBovino = event.target.value === 'Bovino';
          document.getElementById('grupo-f-categoria').classList.toggle('d-none', !esBovino);
          if (!esBovino) document.getElementById('f-categoria').value = '';
          paginaActual = 1;
          renderTabla();
        });

        const selectEstablecimiento = document.getElementById('animal-establecimiento');
        const establecimientoActualId = window.HUACAPP_DATA?.establecimiento_id || '';
        (window.HUACAPP_DATA?.establecimientos || []).forEach((establecimiento) => {
          selectEstablecimiento.add(new Option(establecimiento.nombre, establecimiento.id));
        });
        selectEstablecimiento.value = establecimientoActualId;
        cargarParcelasDeEstablecimiento(selectEstablecimiento.value);
        selectEstablecimiento.addEventListener('change', () => {
          cargarParcelasDeEstablecimiento(selectEstablecimiento.value);
          const parcela = document.getElementById('animal-parcela');
          if (parcela.value && ![...parcela.options].some((o) => o.value === parcela.value)) {
            parcela.value = '';
          }
        });
        const filtroParcela = document.getElementById('f-parcela');
        (window.HUACAPP_DATA?.parcelas || [])
          .filter((parcela) => !establecimientoActualId || parcela.establecimiento_id === establecimientoActualId)
          .forEach((parcela) => {
            filtroParcela.add(new Option(parcela.nombre, parcela.nombre));
          });
        agregarOpciones('animal-dieta', window.HUACAPP_DATA?.dietas || [], (dieta) => dieta.nombre);
        const progenitores = window.HUACAPP_DATA?.progenitores || [];
        agregarOpciones('animal-madre', progenitores, (animal) => animal.nombre, (animal) => animal.sexo === 'Hembra');
        agregarOpciones('animal-padre', progenitores, (animal) => animal.nombre, (animal) => animal.sexo === 'Macho');
        document.getElementById('animal-sexo').addEventListener('change', actualizarCampoDiametro);
        actualizarCampoDiametro();

        const fotoInput = document.getElementById('animal-foto');
        fotoInput.addEventListener('change', () => {
          const archivo = fotoInput.files[0];
          const preview = document.getElementById('foto-preview');
          if (!archivo) return;
          const lector = new FileReader();
          lector.onload = () => {
            preview.innerHTML = `<img src="${lector.result}" alt="Nueva foto" class="img-fluid rounded" style="max-height: 180px; width: 100%; object-fit: contain;">`;
            preview.classList.remove('d-none');
          };
          lector.readAsDataURL(archivo);
          document.getElementById('foto-acciones').classList.add('d-none');
          document.getElementById('animal-eliminar-foto').value = '';
        });

        document.getElementById('btn-eliminar-foto').addEventListener('click', () => {
          const preview = document.getElementById('foto-preview');
          preview.innerHTML = '<div class="text-muted small">Sin imagen cargada</div>';
          preview.classList.remove('d-none');
          fotoInput.value = '';
          document.getElementById('foto-acciones').classList.add('d-none');
          document.getElementById('animal-eliminar-foto').value = '1';
        });

        document.getElementById('modalNuevoAnimal').addEventListener('hidden.bs.modal', () => {
          animalEnEdicion = null;
          document.getElementById('modalNuevoAnimalTitulo').innerHTML = '<i class="bi bi-cow me-2"></i>Nuevo animal';
          document.getElementById('form-nuevo-animal').reset();
          selectEstablecimiento.value = establecimientoActualId;
          cargarParcelasDeEstablecimiento(selectEstablecimiento.value);
          document.getElementById('foto-acciones').classList.add('d-none');
          document.getElementById('foto-preview').classList.add('d-none');
          document.getElementById('animal-eliminar-foto').value = '';
          document.getElementById('grupo-compra').classList.add('d-none');
          document.getElementById('grupo-costo').classList.add('d-none');
          document.getElementById('grupo-venta').classList.add('d-none');
          document.getElementById('grupo-precio-venta').classList.add('d-none');
          document.getElementById('animal-form-error').classList.add('d-none');
        });

        document.getElementById('form-nuevo-animal').addEventListener('submit', async (event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const error = document.getElementById('animal-form-error');
          error.classList.add('d-none');
          const raza = document.getElementById('animal-raza').value.trim();
          if (raza && !/^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/.test(raza)) {
            error.textContent = 'La raza debe comenzar con una letra.';
            error.classList.remove('d-none');
            return;
          }
          try {
            const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1];
            const url = animalEnEdicion ? `/api/animales/${animalEnEdicion.id}/` : '/api/animales/';
            const response = await fetch(url, {
              method: 'POST',
              headers: { 'X-CSRFToken': csrf || '' },
              body: new FormData(form),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'No se pudo guardar el animal.');
            const guardado = result.animal;
            const estabaSeleccionado = animalEnEdicion && animalSeleccionadoId === animalEnEdicion.id;
            if (animalEnEdicion) {
              const index = ANIMALES.findIndex((item) => item.id === animalEnEdicion.id);
              if (index !== -1) ANIMALES[index] = guardado;
              else ANIMALES.push(guardado);
            } else {
              ANIMALES.push(guardado);
            }
            if (estabaSeleccionado) renderFichaAnimal(guardado.id);
            renderTabla();
            bootstrap.Modal.getInstance(document.getElementById('modalNuevoAnimal'))?.hide();
          } catch (exception) {
            error.textContent = exception.message;
            error.classList.remove('d-none');
          }
        });
      });
    
