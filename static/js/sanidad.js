const SANIDAD_DATA = window.GANASTOCK_DATA || {};
const EVENTOS = Array.isArray(SANIDAD_DATA.eventos) ? [...SANIDAD_DATA.eventos] : [];
const ENFERMEDADES = Array.isArray(SANIDAD_DATA.enfermedades) ? SANIDAD_DATA.enfermedades : [];
const DIAGNOSTICOS = Array.isArray(SANIDAD_DATA.diagnosticos) ? SANIDAD_DATA.diagnosticos : [];
const VETERINARIOS = Array.isArray(SANIDAD_DATA.veterinarios) ? SANIDAD_DATA.veterinarios : [];
const LOTES = Array.isArray(SANIDAD_DATA.lotes) ? SANIDAD_DATA.lotes : [];
const ANIMALES = Array.isArray(SANIDAD_DATA.animales) ? SANIDAD_DATA.animales : [];
const TIPOS_EVENTO = SANIDAD_DATA.tipos_evento || ['Vacunación', 'Desparasitación', 'Antibiótico', 'Suplemento', 'Castración', 'Inseminación'];
const ESTADO_BADGE = {
  true: 'text-bg-success',
  false: 'text-bg-warning',
};
const FILAS_POR_PAGINA = 8;
let paginaActual = 1;
let eventoEnEdicion = null;

function formatFecha(iso) {
  if (!iso) return '-';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function parseBoolean(value) {
  return value === true || value === 'true' || value === 'on';
}

const API_EVENTOS_BASE = '/api/sanidad/eventos/';

function getCsrfToken() {
  return document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

function buildEventFormData(evento) {
  const formData = new FormData();
  formData.append('tipo', evento.tipo);
  formData.append('fecha_aplicacion', evento.fecha_aplicacion);
  formData.append('estado', evento.estado ? 'true' : 'false');
  formData.append('animal_id', evento.animal_id);
  formData.append('detalle', evento.detalle || '');

  if (evento.veterinario_id) {
    formData.append('veterinario_id', evento.veterinario_id);
  }
  if (evento.diagnostico_id) {
    formData.append('diagnostico_id', evento.diagnostico_id);
  }
  if (evento.lote_id) {
    formData.append('lote_id', evento.lote_id);
  }
  if (evento.cantidad !== undefined && evento.cantidad !== null && evento.cantidad !== '') {
    formData.append('cantidad', evento.cantidad);
  }
  if (evento.costo_total !== undefined && evento.costo_total !== null && evento.costo_total !== '') {
    formData.append('costo_total', evento.costo_total);
  }
  return formData;
}

async function sendEventoRequest(url, evento) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: buildEventFormData(evento),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Error al procesar el evento sanitario.');
  }
  return data;
}

function setOptions(select, options, includeBlank = false) {
  const html = [];
  if (includeBlank) html.push('<option value="">Todos</option>');
  options.forEach((opt) => {
    html.push(`<option value="${opt.value}">${opt.label}</option>`);
  });
  select.innerHTML = html.join('');
}

function renderKpis() {
  const hoy = new Date();
  const mesActual = hoy.getMonth() + 1;
  const anioActual = hoy.getFullYear();
  const eventosAplicadosMes = EVENTOS.filter((evento) => {
    if (!evento.estado) return false;
    const [anio, mes] = evento.fecha_aplicacion.split('-').map(Number);
    return anio === anioActual && mes === mesActual;
  }).length;
  const proximasAplicaciones = EVENTOS.filter((evento) => {
    if (evento.estado) return false;
    return new Date(evento.fecha_aplicacion) >= new Date(hoy.toISOString().split('T')[0]);
  }).length;

  document.getElementById('kpi-eventos').textContent = EVENTOS.length;
  document.getElementById('kpi-aplicaciones-mes').textContent = eventosAplicadosMes;
  document.getElementById('kpi-proximas').textContent = proximasAplicaciones;
  document.getElementById('kpi-veterinarios').textContent = VETERINARIOS.length;
}

function aplicarFiltros() {
  const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
  const fecha = document.getElementById('f-fecha').value;
  const tipo = document.getElementById('f-tipo').value;
  const veterinario = document.getElementById('f-veterinario').value;
  const estado = document.getElementById('f-estado').value;

  return EVENTOS.filter((evento) => {
    const matchBuscar =
      !buscar ||
      evento.caravana.toLowerCase().includes(buscar) ||
      evento.animal.toLowerCase().includes(buscar) ||
      evento.detalle.toLowerCase().includes(buscar) ||
      evento.tipo.toLowerCase().includes(buscar);
    const matchFecha = !fecha || evento.fecha_aplicacion === fecha;
    const matchTipo = !tipo || evento.tipo === tipo;
    const matchVeterinario = !veterinario || String(evento.veterinario_id) === veterinario;
    const matchEstado = estado === '' || String(evento.estado) === estado;
    return matchBuscar && matchFecha && matchTipo && matchVeterinario && matchEstado;
  }).sort((a, b) => (a.fecha_aplicacion < b.fecha_aplicacion ? 1 : -1));
}

function renderTabla() {
  const datos = aplicarFiltros();
  const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
  if (paginaActual > totalPaginas) paginaActual = totalPaginas;

  const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
  const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

  document.getElementById('tabla-sanidad-body').innerHTML = pagina
    .map(
      (evento) => `
      <tr>
        <td>${formatFecha(evento.fecha_aplicacion)}</td>
        <td>#${evento.caravana}</td>
        <td>${evento.animal}</td>
        <td>${evento.tipo}</td>
        <td>${evento.veterinario}</td>
        <td>${evento.diagnostico}</td>
        <td>${evento.lote}</td>
        <td>${evento.cantidad || '-'}</td>
        <td><span class="badge ${ESTADO_BADGE[evento.estado] || 'text-bg-secondary'}">${evento.estado ? 'Aplicado' : 'Pendiente'}</span></td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-secondary btn-detalle-evento" data-id="${evento.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
          <button class="btn btn-sm btn-outline-primary btn-editar-evento" data-id="${evento.id}" title="Editar"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger btn-eliminar-evento" data-id="${evento.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
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

function getCalendarBounds() {
  const fechas = EVENTOS.map((evento) => new Date(evento.fecha_aplicacion));
  if (!fechas.length) return { year: new Date().getFullYear(), month: new Date().getMonth() };
  fechas.sort((a, b) => a - b);
  const earliest = fechas[0];
  return { year: earliest.getFullYear(), month: earliest.getMonth() };
}

function renderCalendar() {
  const eventosVisibles = aplicarFiltros();
  const { year, month } = getCalendarBounds();
  const primerDiaSemana = new Date(year, month, 1).getDay();
  const diasMes = new Date(year, month + 1, 0).getDate();

  const eventosPorDia = eventosVisibles.reduce((acc, evento) => {
    if (!evento.fecha_aplicacion) return acc;
    acc[evento.fecha_aplicacion] = acc[evento.fecha_aplicacion] || [];
    acc[evento.fecha_aplicacion].push(evento);
    return acc;
  }, {});

  const nombreMes = new Date(year, month, 1).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });
  const titulo = document.getElementById('calendario-titulo');
  if (titulo) {
    titulo.textContent = `${nombreMes.charAt(0).toUpperCase()}${nombreMes.slice(1)}`;
  }

  let html = ['D', 'L', 'M', 'M', 'J', 'V', 'S'].map((diasemana) => `<div class="day-label">${diasemana}</div>`).join('');
  for (let i = 0; i < primerDiaSemana; i += 1) {
    html += '<div class="day-cell empty"></div>';
  }
  for (let dia = 1; dia <= diasMes; dia += 1) {
    const fecha = `${year}-${String(month + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    const eventos = eventosPorDia[fecha] || [];
    const clase = eventos.length ? 'has-events' : '';
    html += `
      <button type="button" class="day-cell ${clase}" data-fecha="${fecha}">
        <span>${dia}</span>
        ${eventos.length ? `<small class="text-muted">${eventos.length} evento${eventos.length > 1 ? 's' : ''}</small>` : ''}
      </button>`;
  }

  const grid = document.getElementById('calendario-grid');
  grid.innerHTML = html;
  grid.querySelectorAll('.day-cell[data-fecha]').forEach((cell) => {
    cell.addEventListener('click', () => {
      document.querySelectorAll('.day-cell.selected').forEach((selected) => selected.classList.remove('selected'));
      cell.classList.add('selected');
      showCalendarDetails(cell.dataset.fecha);
    });
  });
}

function showCalendarDetails(fecha) {
  const eventos = EVENTOS.filter((evento) => evento.fecha_aplicacion === fecha);
  const detalle = document.getElementById('calendario-detalle');
  if (!eventos.length) {
    detalle.textContent = `No hay eventos en ${formatFecha(fecha)}`;
    return;
  }
  detalle.innerHTML = `
    <div><strong>${eventos.length} evento${eventos.length > 1 ? 's' : ''} el ${formatFecha(fecha)}</strong></div>
    <ul class="list-unstyled small mb-0">
      ${eventos
        .map(
          (evento) => `<li class="mb-2"><span class="badge ${ESTADO_BADGE[evento.estado] || 'text-bg-secondary'} me-2">${evento.estado ? 'Aplicado' : 'Pendiente'}</span> ${evento.tipo} - #${evento.caravana} ${evento.animal} ${evento.veterinario ? `(${evento.veterinario})` : ''}</li>`,
        )
        .join('')}
    </ul>`;
}

function toggleVista(vista) {
  const calendario = document.getElementById('sanidad-vista-calendario');
  const lista = document.getElementById('sanidad-vista-lista');
  const btnCalendario = document.getElementById('btn-vista-calendario');
  const btnLista = document.getElementById('btn-vista-lista');

  if (vista === 'calendario') {
    calendario.style.display = '';
    lista.style.display = 'none';
    btnCalendario.classList.add('active');
    btnCalendario.classList.replace('btn-outline-secondary', 'btn-outline-primary');
    btnLista.classList.remove('active');
    btnLista.classList.replace('btn-outline-primary', 'btn-outline-secondary');
  } else {
    calendario.style.display = 'none';
    lista.style.display = '';
    btnLista.classList.add('active');
    btnLista.classList.replace('btn-outline-secondary', 'btn-outline-primary');
    btnCalendario.classList.remove('active');
    btnCalendario.classList.replace('btn-outline-primary', 'btn-outline-secondary');
  }
}

function renderVeterinarios() {
  const tbody = document.getElementById('veterinarios-body');
  if (!VETERINARIOS.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-secondary py-3">No hay veterinarios registrados.</td></tr>';
    return;
  }
  tbody.innerHTML = VETERINARIOS.map((vet) => `
    <tr>
      <td>${vet.nombre_completo}</td>
      <td>${vet.correo_electronico || '-'}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-secondary btn-detalle-veterinario" data-id="${vet.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
        <button class="btn btn-sm btn-outline-primary btn-editar-veterinario" data-id="${vet.id}" title="Editar"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger btn-eliminar-veterinario" data-id="${vet.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
      </td>
    </tr>
  `).join('');
}

function renderEnfermedades() {
  const tbody = document.getElementById('enfermedades-body');
  if (!ENFERMEDADES.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-secondary py-3">No hay enfermedades registradas.</td></tr>';
    return;
  }
  tbody.innerHTML = ENFERMEDADES.map((enf) => `
    <tr>
      <td>${enf.nombre}</td>
      <td>${enf.es_zoonotica ? 'Sí' : 'No'}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-secondary btn-detalle-enfermedad" data-id="${enf.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
        <button class="btn btn-sm btn-outline-primary btn-editar-enfermedad" data-id="${enf.id}" title="Editar"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger btn-eliminar-enfermedad" data-id="${enf.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
      </td>
    </tr>
  `).join('');
}

function renderDiagnosticos() {
  const tbody = document.getElementById('diagnosticos-body');
  if (!DIAGNOSTICOS.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary py-3">No hay diagnósticos registrados.</td></tr>';
    return;
  }
  tbody.innerHTML = DIAGNOSTICOS.map((diag) => `
    <tr>
      <td>#${diag.caravana} - ${diag.animal}</td>
      <td>${diag.enfermedad}</td>
      <td>${diag.estado_actual}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-secondary btn-detalle-diagnostico" data-id="${diag.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
        <button class="btn btn-sm btn-outline-primary btn-editar-diagnostico" data-id="${diag.id}" title="Editar"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger btn-eliminar-diagnostico" data-id="${diag.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
      </td>
    </tr>
  `).join('');
}

function bindEnfermedadesTable() {
  const tbody = document.getElementById('enfermedades-body');
  tbody.querySelectorAll('.btn-detalle-enfermedad').forEach((btn) => {
    btn.addEventListener('click', () => {
      const enfermedad = ENFERMEDADES.find((item) => String(item.id) === btn.dataset.id);
      if (enfermedad) abrirDetalleCrud('Enfermedad', `
        <p><strong>Nombre:</strong> ${enfermedad.nombre}</p>
        <p><strong>Zoonótica:</strong> ${enfermedad.es_zoonotica ? 'Sí' : 'No'}</p>
        <p><strong>Descripción:</strong> ${enfermedad.descripcion || '-'}</p>
      `);
    });
  });
  tbody.querySelectorAll('.btn-editar-enfermedad').forEach((btn) => {
    btn.addEventListener('click', () => {
      const enfermedad = ENFERMEDADES.find((item) => String(item.id) === btn.dataset.id);
      if (enfermedad) openEnfermedadModal(enfermedad);
    });
  });
  tbody.querySelectorAll('.btn-eliminar-enfermedad').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (confirm('¿Eliminar esta enfermedad?')) {
        eliminarEnfermedad(btn.dataset.id);
      }
    });
  });
}

function bindDiagnosticosTable() {
  const tbody = document.getElementById('diagnosticos-body');
  tbody.querySelectorAll('.btn-detalle-diagnostico').forEach((btn) => {
    btn.addEventListener('click', () => {
      const diagnostico = DIAGNOSTICOS.find((item) => String(item.id) === btn.dataset.id);
      if (diagnostico) abrirDetalleCrud('Diagnóstico', `
        <p><strong>Animal:</strong> #${diagnostico.caravana} - ${diagnostico.animal}</p>
        <p><strong>Enfermedad:</strong> ${diagnostico.enfermedad}</p>
        <p><strong>Fecha detección:</strong> ${formatFecha(diagnostico.fecha_deteccion)}</p>
        <p><strong>Estado actual:</strong> ${diagnostico.estado_actual}</p>
        <p><strong>Observaciones:</strong> ${diagnostico.observaciones || '-'}</p>
      `);
    });
  });
  tbody.querySelectorAll('.btn-editar-diagnostico').forEach((btn) => {
    btn.addEventListener('click', () => {
      const diagnostico = DIAGNOSTICOS.find((item) => String(item.id) === btn.dataset.id);
      if (diagnostico) openDiagnosticoModal(diagnostico);
    });
  });
  tbody.querySelectorAll('.btn-eliminar-diagnostico').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (confirm('¿Eliminar este diagnóstico?')) {
        eliminarDiagnostico(btn.dataset.id);
      }
    });
  });
}

function bindVeterinariosTable() {
  const tbody = document.getElementById('veterinarios-body');
  tbody.querySelectorAll('.btn-detalle-veterinario').forEach((btn) => {
    btn.addEventListener('click', () => {
      const veterinario = VETERINARIOS.find((item) => String(item.id) === btn.dataset.id);
      if (veterinario) abrirDetalleCrud('Veterinario', `
        <p><strong>Nombre:</strong> ${veterinario.nombre_completo}</p>
        <p><strong>Correo:</strong> ${veterinario.correo_electronico || '-'}</p>
        <p><strong>Teléfono:</strong> ${veterinario.telefono || '-'}</p>
        <p><strong>Fecha de nacimiento:</strong> ${formatFecha(veterinario.fecha_nacimiento)}</p>
      `);
    });
  });
  tbody.querySelectorAll('.btn-editar-veterinario').forEach((btn) => {
    btn.addEventListener('click', () => {
      const veterinario = VETERINARIOS.find((item) => String(item.id) === btn.dataset.id);
      if (veterinario) openVeterinarioModal(veterinario);
    });
  });
  tbody.querySelectorAll('.btn-eliminar-veterinario').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (confirm('¿Eliminar este veterinario?')) {
        eliminarVeterinario(btn.dataset.id);
      }
    });
  });
}

function abrirDetalleCrud(titulo, contenidoHtml) {
  document.getElementById('detalle-crud-title').textContent = titulo;
  document.getElementById('detalle-crud-body').innerHTML = contenidoHtml;
  const modal = new bootstrap.Modal(document.getElementById('modalDetalleCrud'));
  modal.show();
}

function buildEntityFormData(data) {
  const formData = new FormData();
  Object.entries(data).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      formData.append(key, value);
    }
  });
  return formData;
}

function buildEnfermedadFormData(enfermedad) {
  return buildEntityFormData({
    nombre: enfermedad.nombre,
    es_zoonotica: enfermedad.es_zoonotica ? 'true' : 'false',
    descripcion: enfermedad.descripcion || '',
  });
}

function buildDiagnosticoFormData(diagnostico) {
  return buildEntityFormData({
    animal_id: diagnostico.animal_id,
    enfermedad_id: diagnostico.enfermedad_id,
    fecha_deteccion: diagnostico.fecha_deteccion,
    estado_actual: diagnostico.estado_actual,
    observaciones: diagnostico.observaciones || '',
  });
}

function buildVeterinarioFormData(veterinario) {
  return buildEntityFormData({
    nombre: veterinario.nombre,
    apellido: veterinario.apellido,
    correo_electronico: veterinario.correo_electronico || '',
    telefono: veterinario.telefono || '',
    fecha_nacimiento: veterinario.fecha_nacimiento || '',
  });
}

const modalRegistrarEnfermedad = new bootstrap.Modal(document.getElementById('modalRegistrarEnfermedad'));
const modalRegistrarDiagnostico = new bootstrap.Modal(document.getElementById('modalRegistrarDiagnostico'));
const modalRegistrarVeterinario = new bootstrap.Modal(document.getElementById('modalRegistrarVeterinario'));

function resetEnfermedadForm() {
  document.getElementById('enfermedad-id').value = '';
  document.getElementById('e-nombre').value = '';
  document.getElementById('e-zoonotica').checked = false;
  document.getElementById('e-descripcion').value = '';
}

function resetDiagnosticoForm() {
  document.getElementById('diagnostico-id').value = '';
  document.getElementById('d-animal').value = ANIMALES[0]?.id || '';
  document.getElementById('d-enfermedad').value = ENFERMEDADES[0]?.id || '';
  document.getElementById('d-fecha-deteccion').value = new Date().toISOString().split('T')[0];
  document.getElementById('d-estado-actual').value = 'En tratamiento';
  document.getElementById('d-observaciones').value = '';
}

function resetVeterinarioForm() {
  document.getElementById('veterinario-id').value = '';
  document.getElementById('v-nombre').value = '';
  document.getElementById('v-apellido').value = '';
  document.getElementById('v-correo').value = '';
  document.getElementById('v-telefono').value = '';
  document.getElementById('v-fecha-nacimiento').value = '';
}

function renderAnimalOptions(select, filter = '') {
  const normalizedFilter = filter.trim().toLowerCase();
  const options = ANIMALES
    .filter((a) => !normalizedFilter || String(a.caravana).toLowerCase().includes(normalizedFilter))
    .sort((a, b) => String(a.caravana).localeCompare(String(b.caravana), undefined, { numeric: true }))
    .map((a) => ({ value: a.id, label: `#${a.caravana} - ${a.nombre || 'S/N'}` }));
  if (!options.length) {
    select.innerHTML = '<option value="">No se encontraron animales</option>';
    return;
  }
  setOptions(select, options, false);
}

function updateDiagnosticoSelects() {
  renderAnimalOptions(document.getElementById('d-animal'));
  setOptions(document.getElementById('d-enfermedad'), ENFERMEDADES.map((e) => ({ value: e.id, label: e.nombre })), false);
}

function openEnfermedadModal(enfermedad = null) {
  document.getElementById('modal-enfermedad-title').textContent = enfermedad ? 'Editar Enfermedad' : 'Registrar Enfermedad';
  if (!enfermedad) {
    resetEnfermedadForm();
  } else {
    document.getElementById('enfermedad-id').value = enfermedad.id;
    document.getElementById('e-nombre').value = enfermedad.nombre;
    document.getElementById('e-zoonotica').checked = enfermedad.es_zoonotica;
    document.getElementById('e-descripcion').value = enfermedad.descripcion || '';
  }
  modalRegistrarEnfermedad.show();
}

function openDiagnosticoModal(diagnostico = null) {
  document.getElementById('modal-diagnostico-title').textContent = diagnostico ? 'Editar Diagnóstico' : 'Registrar Diagnóstico';
  document.getElementById('d-animal-search').value = '';
  updateDiagnosticoSelects();
  if (!diagnostico) {
    resetDiagnosticoForm();
  } else {
    document.getElementById('diagnostico-id').value = diagnostico.id;
    document.getElementById('d-animal').value = diagnostico.animal_id;
    document.getElementById('d-enfermedad').value = diagnostico.enfermedad_id;
    document.getElementById('d-fecha-deteccion').value = diagnostico.fecha_deteccion;
    document.getElementById('d-estado-actual').value = diagnostico.estado_actual;
    document.getElementById('d-observaciones').value = diagnostico.observaciones || '';
  }
  modalRegistrarDiagnostico.show();
}

function openVeterinarioModal(veterinario = null) {
  document.getElementById('modal-veterinario-title').textContent = veterinario ? 'Editar Veterinario' : 'Registrar Veterinario';
  if (!veterinario) {
    resetVeterinarioForm();
  } else {
    document.getElementById('veterinario-id').value = veterinario.id;
    document.getElementById('v-nombre').value = veterinario.nombre;
    document.getElementById('v-apellido').value = veterinario.apellido;
    document.getElementById('v-correo').value = veterinario.correo_electronico || '';
    document.getElementById('v-telefono').value = veterinario.telefono || '';
    document.getElementById('v-fecha-nacimiento').value = veterinario.fecha_nacimiento || '';
  }
  modalRegistrarVeterinario.show();
}

async function guardarEnfermedad() {
  const id = document.getElementById('enfermedad-id').value;
  const nombre = document.getElementById('e-nombre').value.trim();
  const es_zoonotica = document.getElementById('e-zoonotica').checked;
  const descripcion = document.getElementById('e-descripcion').value.trim();

  if (!nombre) {
    alert('El nombre de la enfermedad es obligatorio.');
    return;
  }

  const url = id ? `/api/sanidad/enfermedades/${id}/` : '/api/sanidad/enfermedades/';
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: buildEnfermedadFormData({ nombre, es_zoonotica, descripcion }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'No se pudo guardar la enfermedad.');
    return;
  }
  if (id) {
    const index = ENFERMEDADES.findIndex((item) => String(item.id) === String(id));
    if (index !== -1) ENFERMEDADES[index] = data.enfermedad;
  } else {
    ENFERMEDADES.unshift(data.enfermedad);
  }
  modalRegistrarEnfermedad.hide();
  renderEnfermedades();
  bindEnfermedadesTable();
  updateDiagnosticoSelects();
}

async function guardarDiagnostico() {
  const id = document.getElementById('diagnostico-id').value;
  const animal_id = document.getElementById('d-animal').value;
  const enfermedad_id = document.getElementById('d-enfermedad').value;
  const fecha_deteccion = document.getElementById('d-fecha-deteccion').value;
  const estado_actual = document.getElementById('d-estado-actual').value;
  const observaciones = document.getElementById('d-observaciones').value.trim();

  if (!animal_id || !enfermedad_id || !fecha_deteccion) {
    alert('Debe completar animal, enfermedad y fecha de detección.');
    return;
  }

  const url = id ? `/api/sanidad/diagnosticos/${id}/` : '/api/sanidad/diagnosticos/';
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: buildDiagnosticoFormData({ animal_id, enfermedad_id, fecha_deteccion, estado_actual, observaciones }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'No se pudo guardar el diagnóstico.');
    return;
  }
  if (id) {
    const index = DIAGNOSTICOS.findIndex((item) => String(item.id) === String(id));
    if (index !== -1) DIAGNOSTICOS[index] = data.diagnostico;
  } else {
    DIAGNOSTICOS.unshift(data.diagnostico);
  }
  modalRegistrarDiagnostico.hide();
  renderDiagnosticos();
  bindDiagnosticosTable();
}

async function guardarVeterinario() {
  const id = document.getElementById('veterinario-id').value;
  const nombre = document.getElementById('v-nombre').value.trim();
  const apellido = document.getElementById('v-apellido').value.trim();
  const correo_electronico = document.getElementById('v-correo').value.trim();
  const telefono = document.getElementById('v-telefono').value.trim();
  const fecha_nacimiento = document.getElementById('v-fecha-nacimiento').value;

  if (!nombre || !apellido) {
    alert('Nombre y apellido son obligatorios.');
    return;
  }

  const url = id ? `/api/sanidad/veterinarios/${id}/` : '/api/sanidad/veterinarios/';
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: buildVeterinarioFormData({ nombre, apellido, correo_electronico, telefono, fecha_nacimiento }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'No se pudo guardar el veterinario.');
    return;
  }
  if (id) {
    const index = VETERINARIOS.findIndex((item) => String(item.id) === String(id));
    if (index !== -1) VETERINARIOS[index] = data.veterinario;
  } else {
    VETERINARIOS.unshift(data.veterinario);
  }
  modalRegistrarVeterinario.hide();
  renderVeterinarios();
  bindVeterinariosTable();
  renderFiltros();
}

async function eliminarEnfermedad(id) {
  const response = await fetch(`/api/sanidad/enfermedades/${id}/eliminar/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'No se pudo eliminar la enfermedad.');
    return;
  }
  const index = ENFERMEDADES.findIndex((item) => String(item.id) === String(id));
  if (index !== -1) ENFERMEDADES.splice(index, 1);
  renderEnfermedades();
  bindEnfermedadesTable();
  updateDiagnosticoSelects();
}

async function eliminarDiagnostico(id) {
  const response = await fetch(`/api/sanidad/diagnosticos/${id}/eliminar/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'No se pudo eliminar el diagnóstico.');
    return;
  }
  const index = DIAGNOSTICOS.findIndex((item) => String(item.id) === String(id));
  if (index !== -1) DIAGNOSTICOS.splice(index, 1);
  renderDiagnosticos();
  bindDiagnosticosTable();
}

async function eliminarVeterinario(id) {
  const response = await fetch(`/api/sanidad/veterinarios/${id}/eliminar/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'No se pudo eliminar el veterinario.');
    return;
  }
  const index = VETERINARIOS.findIndex((item) => String(item.id) === String(id));
  if (index !== -1) VETERINARIOS.splice(index, 1);
  renderVeterinarios();
  bindVeterinariosTable();
  renderFiltros();
}

function renderFiltros() {
  const tipoOptions = TIPOS_EVENTO.map((tipo) => ({ value: tipo, label: tipo }));
  setOptions(document.getElementById('f-tipo'), tipoOptions, true);
  setOptions(document.getElementById('s-tipo'), tipoOptions, false);

  const veterinarioOptions = VETERINARIOS.map((v) => ({ value: v.id, label: v.nombre_completo }));
  setOptions(document.getElementById('f-veterinario'), veterinarioOptions, true);
  setOptions(document.getElementById('s-veterinario'), [{ value: '', label: 'Sin veterinario' }, ...veterinarioOptions]);

  const diagnosticoOptions = [{ value: '', label: 'Sin diagnóstico' }, ...DIAGNOSTICOS.map((d) => ({ value: d.id, label: `${d.enfermedad} - ${d.animal}` }))];
  setOptions(document.getElementById('s-diagnostico'), diagnosticoOptions, false);

  renderAnimalOptions(document.getElementById('s-animal'));

  const loteOptions = [{ value: '', label: 'Sin lote' }, ...LOTES.map((l) => ({ value: l.id, label: `${l.insumo} (${l.stock} u)` }))];
  setOptions(document.getElementById('s-lote'), loteOptions, false);
}

const modalRegistrarEventoEl = document.getElementById('modalRegistrarEvento');
const modalRegistrarEvento = new bootstrap.Modal(modalRegistrarEventoEl);

function resetEventoForm() {
  document.getElementById('form-evento').reset();
  document.getElementById('evento-id').value = '';
  document.getElementById('s-tipo').value = TIPOS_EVENTO[0] || '';
  document.getElementById('s-estado').value = 'true';
  document.getElementById('d-fecha').value = new Date().toISOString().split('T')[0];
  document.getElementById('s-animal-search').value = '';
  renderAnimalOptions(document.getElementById('s-animal'));
  document.getElementById('s-animal').value = ANIMALES[0]?.id || '';
  document.getElementById('s-veterinario').value = '';
  document.getElementById('s-diagnostico').value = '';
  document.getElementById('s-lote').value = '';
  document.getElementById('i-cantidad').value = '';
  document.getElementById('i-costo').value = '';
  document.getElementById('t-detalle').value = '';
}

function openEventoModal(evento = null) {
  eventoEnEdicion = evento;
  const modalTitle = document.getElementById('modal-evento-title');
  modalTitle.textContent = evento ? 'Editar Evento' : 'Registrar Evento';

  if (!evento) {
    resetEventoForm();
  } else {
    document.getElementById('evento-id').value = evento.id;
    document.getElementById('s-tipo').value = evento.tipo;
    document.getElementById('d-fecha').value = evento.fecha_aplicacion;
    document.getElementById('s-estado').value = String(evento.estado);
    document.getElementById('s-animal').value = evento.animal_id || ANIMALES[0]?.id || '';
    document.getElementById('s-veterinario').value = evento.veterinario_id || '';
    document.getElementById('s-diagnostico').value = evento.diagnostico_id || '';
    document.getElementById('s-lote').value = evento.lote_id || '';
    document.getElementById('i-cantidad').value = evento.cantidad || '';
    document.getElementById('i-costo').value = evento.costo_total || '';
    document.getElementById('t-detalle').value = evento.detalle || '';
  }

  modalRegistrarEvento.show();
}

function abrirDetalleEvento(evento) {
  document.getElementById('detalle-caravana').textContent = `#${evento.caravana}`;
  document.getElementById('detalle-animal').textContent = evento.animal;
  document.getElementById('detalle-tipo').textContent = evento.tipo;
  document.getElementById('detalle-estado').textContent = evento.estado ? 'Aplicado' : 'Pendiente';
  document.getElementById('detalle-fecha').textContent = formatFecha(evento.fecha_aplicacion);
  document.getElementById('detalle-veterinario').textContent = evento.veterinario;
  document.getElementById('detalle-diagnostico').textContent = evento.diagnostico;
  document.getElementById('detalle-lote').textContent = evento.lote;
  document.getElementById('detalle-cantidad').textContent = evento.cantidad || '-';
  document.getElementById('detalle-costo').textContent = evento.costo_total || '-';
  document.getElementById('detalle-observaciones').textContent = evento.detalle || '-';

  const modal = new bootstrap.Modal(document.getElementById('modalDetalleEvento'));
  modal.show();
}

async function guardarEvento() {
  const id = document.getElementById('evento-id').value;
  const tipo = document.getElementById('s-tipo').value;
  const fecha_aplicacion = document.getElementById('d-fecha').value;
  const estado = parseBoolean(document.getElementById('s-estado').value);
  const animalId = document.getElementById('s-animal').value;
  const veterinarioId = document.getElementById('s-veterinario').value;
  const diagnosticoId = document.getElementById('s-diagnostico').value;
  const loteId = document.getElementById('s-lote').value;
  const cantidad = document.getElementById('i-cantidad').value;
  const costo_total = document.getElementById('i-costo').value;
  const detalle = document.getElementById('t-detalle').value;

  const animal = ANIMALES.find((a) => String(a.id) === String(animalId));
  const diag = DIAGNOSTICOS.find((d) => String(d.id) === String(diagnosticoId));
  const lote = LOTES.find((l) => String(l.id) === String(loteId));

  if (!tipo || !fecha_aplicacion || !animal) {
    alert('Debe completar tipo, fecha y animal.');
    return;
  }

  const eventoNuevo = {
    id,
    detalle,
    tipo,
    fecha_aplicacion,
    estado,
    costo_total: costo_total || '0',
    animal_id: animal.id,
    veterinario_id: veterinarioId || null,
    diagnostico_id: diagnosticoId || null,
    lote_id: loteId || null,
    cantidad: cantidad || '',
  };

  try {
    let data;
    if (id && !String(id).startsWith('tmp-')) {
      data = await sendEventoRequest(`${API_EVENTOS_BASE}${id}/`, eventoNuevo);
      const index = EVENTOS.findIndex((evento) => String(evento.id) === String(id));
      if (index !== -1) {
        EVENTOS[index] = data.evento;
      }
    } else {
      data = await sendEventoRequest(API_EVENTOS_BASE, eventoNuevo);
      EVENTOS.unshift(data.evento);
    }
    renderTabla();
    const modal = bootstrap.Modal.getInstance(document.getElementById('modalRegistrarEvento'));
    if (modal) modal.hide();
  } catch (error) {
    alert(error.message);
  }
}

async function eliminarEvento(id) {
  if (!confirm('¿Eliminar este evento sanitario?')) {
    return;
  }

  try {
    const response = await fetch(`${API_EVENTOS_BASE}${id}/eliminar/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Error al eliminar el evento.');
    }
    const index = EVENTOS.findIndex((evento) => String(evento.id) === String(id));
    if (index !== -1) {
      EVENTOS.splice(index, 1);
    }
    renderTabla();
  } catch (error) {
    alert(error.message);
  }
}

function bindEventosTabla() {
  const tbody = document.getElementById('tabla-sanidad-body');
  tbody.querySelectorAll('.btn-detalle-evento').forEach((btn) => {
    btn.addEventListener('click', () => {
      const evento = EVENTOS.find((item) => String(item.id) === btn.dataset.id);
      if (evento) abrirDetalleEvento(evento);
    });
  });
  tbody.querySelectorAll('.btn-editar-evento').forEach((btn) => {
    btn.addEventListener('click', () => {
      const evento = EVENTOS.find((item) => String(item.id) === btn.dataset.id);
      if (evento) openEventoModal(evento);
    });
  });
  tbody.querySelectorAll('.btn-eliminar-evento').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (confirm('¿Eliminar este evento sanitario?')) {
        eliminarEvento(btn.dataset.id);
      }
    });
  });
}

function setupListeners() {
  document.getElementById('btn-guardar-evento').addEventListener('click', guardarEvento);
  document.getElementById('btn-registrar-evento').addEventListener('click', () => openEventoModal());
  document.getElementById('btn-registrar-enfermedad').addEventListener('click', () => openEnfermedadModal());
  document.getElementById('btn-registrar-diagnostico').addEventListener('click', () => openDiagnosticoModal());
  document.getElementById('btn-registrar-veterinario').addEventListener('click', () => openVeterinarioModal());
  document.getElementById('d-animal-search').addEventListener('input', (event) => renderAnimalOptions(document.getElementById('d-animal'), event.target.value));
  document.getElementById('s-animal-search').addEventListener('input', (event) => renderAnimalOptions(document.getElementById('s-animal'), event.target.value));
  document.getElementById('btn-vista-calendario').addEventListener('click', () => toggleVista('calendario'));
  document.getElementById('btn-vista-lista').addEventListener('click', () => toggleVista('lista'));

  document.getElementById('btn-guardar-enfermedad').addEventListener('click', guardarEnfermedad);
  document.getElementById('btn-guardar-diagnostico').addEventListener('click', guardarDiagnostico);
  document.getElementById('btn-guardar-veterinario').addEventListener('click', guardarVeterinario);

  ['f-buscar', 'f-fecha', 'f-tipo', 'f-veterinario', 'f-estado'].forEach((id) => {
    document.getElementById(id).addEventListener('input', () => {
      paginaActual = 1;
      renderTabla();
      bindEventosTabla();
      renderCalendar();
    });
  });

  document.getElementById('f-limpiar').addEventListener('click', () => {
    ['f-buscar', 'f-fecha', 'f-tipo', 'f-veterinario', 'f-estado'].forEach((id) => {
      document.getElementById(id).value = '';
    });
    paginaActual = 1;
    renderTabla();
    bindEventosTabla();
    renderCalendar();
  });
}

function refresh() {
  renderKpis();
  renderFiltros();
  renderTabla();
  bindEventosTabla();
  renderCalendar();
  renderEnfermedades();
  bindEnfermedadesTable();
  renderDiagnosticos();
  bindDiagnosticosTable();
  renderVeterinarios();
  bindVeterinariosTable();
}

document.addEventListener('DOMContentLoaded', () => {
  setupListeners();
  refresh();
});
