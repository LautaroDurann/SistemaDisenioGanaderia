const SANIDAD_DATA = window.HUACAPP_DATA || {};
const EVENTOS = Array.isArray(SANIDAD_DATA.eventos) ? [...SANIDAD_DATA.eventos] : [];
const ENFERMEDADES = Array.isArray(SANIDAD_DATA.enfermedades) ? SANIDAD_DATA.enfermedades : [];
const DIAGNOSTICOS = Array.isArray(SANIDAD_DATA.diagnosticos) ? SANIDAD_DATA.diagnosticos : [];
const VETERINARIOS = Array.isArray(SANIDAD_DATA.veterinarios) ? SANIDAD_DATA.veterinarios : [];
const LOTES = Array.isArray(SANIDAD_DATA.lotes) ? SANIDAD_DATA.lotes : [];
const INSUMOS = Array.isArray(SANIDAD_DATA.insumos) ? SANIDAD_DATA.insumos : [];
const ANIMALES = Array.isArray(SANIDAD_DATA.animales) ? SANIDAD_DATA.animales : [];
const defaultTiposEvento = ['Vacunación', 'Desparasitación', 'Antibiótico', 'Suplemento', 'Castración', 'Otro'];
const TIPOS_EVENTO = Array.isArray(SANIDAD_DATA.tipos_evento)
  ? [...new Set([...SANIDAD_DATA.tipos_evento, 'Otro'])]
  : defaultTiposEvento;
const ESTADO_BADGE = {
  true: 'text-bg-success',
  false: 'text-bg-warning',
};
const FILAS_POR_PAGINA = 8;
let paginaActual = 1;
let eventoEnEdicion = null;
let guardandoEvento = false;
let seleccionAnimalesEvento = new Set();
let diagnosticoBloqueo = null;
let fechaSeleccionada = null;

function formatFecha(iso) {
  if (!iso) return '-';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function parseBoolean(value) {
  return value === true || value === 'true' || value === 'on';
}

function getSelectedLote() {
  const loteId = document.getElementById('s-lote').value;
  return LOTES.find((lote) => String(lote.id) === String(loteId)) || null;
}

function updateStockWarning() {
  const warningEl = document.getElementById('s-stock-warning');
  if (!warningEl) return;
  const lote = getSelectedLote();
  const cantidadValue = document.getElementById('i-cantidad').value;
  const cantidad = parseFloat(cantidadValue);
  if (lote && !Number.isNaN(cantidad) && cantidad > 0 && lote.stock !== undefined && Number(cantidad) > Number(lote.stock)) {
    warningEl.textContent = `Stock insuficiente: el lote seleccionado tiene solo ${lote.stock} unidad${lote.stock === 1 ? '' : 'es'} disponibles.`;
    warningEl.classList.remove('d-none');
    return;
  }
  warningEl.textContent = '';
  warningEl.classList.add('d-none');
}

function updateEstadoByFecha() {
  const fecha = document.getElementById('d-fecha').value;
  const estadoSelect = document.getElementById('s-estado');
  const hoy = new Date(new Date().toISOString().split('T')[0]);
  const fechaEvento = fecha ? new Date(fecha) : null;
  const esFuturo = fechaEvento && fechaEvento > hoy;
  if (esFuturo) {
    estadoSelect.value = 'false';
    estadoSelect.disabled = true;
  } else {
    estadoSelect.disabled = false;
  }
}

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
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
  formData.append('detalle', evento.detalle || '');

  if (Array.isArray(evento.animal_ids) && evento.animal_ids.length) {
    evento.animal_ids.forEach((animalId) => formData.append('animales', animalId));
  } else if (evento.animal_id) {
    formData.append('animales', evento.animal_id);
  }

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
    const selected = opt.selected ? ' selected' : '';
    html.push(`<option value="${opt.value}"${selected}>${opt.label}</option>`);
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
        <td>${evento.caravana}</td>
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

function getCalendarBounds(monthSelectorValue) {
  if (monthSelectorValue) {
    const [year, month] = monthSelectorValue.split('-').map(Number);
    return { year, month: month - 1 };
  }
  const hoy = new Date();
  return { year: hoy.getFullYear(), month: hoy.getMonth() };
}

function renderCalendar() {
  const eventosVisibles = aplicarFiltros();
  const mesSeleccionado = document.getElementById('calendario-mes').value;
  const { year, month } = getCalendarBounds(mesSeleccionado);
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
  const mesSelector = document.getElementById('calendario-mes');
  if (mesSelector) {
    mesSelector.value = `${year}-${String(month + 1).padStart(2, '0')}`;
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
    if (cell.dataset.fecha === fechaSeleccionada) {
      cell.classList.add('selected');
    }
    cell.addEventListener('click', () => {
      document.querySelectorAll('.day-cell.selected').forEach((selected) => selected.classList.remove('selected'));
      cell.classList.add('selected');
      fechaSeleccionada = cell.dataset.fecha;
      showCalendarDetails(cell.dataset.fecha);
    });
  });
}

function showCalendarDetails(fecha) {
  const eventos = aplicarFiltros().filter((evento) => evento.fecha_aplicacion === fecha);
  const detalle = document.getElementById('calendario-detalle');
  if (!eventos.length) {
    detalle.textContent = `No hay eventos en ${formatFecha(fecha)}`;
    return;
  }

  detalle.innerHTML = `
    <div class="mb-3"><strong>${eventos.length} evento${eventos.length > 1 ? 's' : ''} el ${formatFecha(fecha)}</strong></div>
    <div class="table-responsive">
      <table class="table table-sm table-hover mb-0">
        <thead class="table-light"><tr>
          <th>Fecha</th>
          <th>Animal</th>
          <th>Tipo</th>
          <th>Veterinario</th>
          <th>Diagnóstico</th>
          <th>Lote</th>
          <th>Cantidad</th>
          <th>Estado</th>
          <th class="text-end">Acciones</th>
        </tr></thead>
        <tbody>
          ${eventos
            .map((evento) => `
              <tr>
                <td>${formatFecha(evento.fecha_aplicacion)}</td>
                <td>${escapeHtml(evento.caravana || evento.animal || '-')}</td>
                <td>${escapeHtml(evento.tipo || '-')}</td>
                <td>${escapeHtml(evento.veterinario || '-')}</td>
                <td>${escapeHtml(evento.diagnostico || '-')}</td>
                <td>${escapeHtml(evento.lote || '-')}</td>
                <td>${escapeHtml(evento.cantidad || '-')}</td>
                <td><span class="badge ${ESTADO_BADGE[evento.estado] || 'text-bg-secondary'}">${evento.estado ? 'Aplicado' : 'Pendiente'}</span></td>
                <td class="text-end">
                  <button type="button" class="btn btn-sm btn-outline-secondary btn-detalle-evento" data-id="${escapeHtml(evento.id)}" title="Ver detalle"><i class="bi bi-eye"></i></button>
                  <button type="button" class="btn btn-sm btn-outline-primary btn-editar-evento" data-id="${escapeHtml(evento.id)}" title="Editar"><i class="bi bi-pencil"></i></button>
                  <button type="button" class="btn btn-sm btn-outline-danger btn-eliminar-evento" data-id="${escapeHtml(evento.id)}" title="Eliminar"><i class="bi bi-trash"></i></button>
                </td>
              </tr>`)
            .join('')}
        </tbody>
      </table>
    </div>`;

  detalle.querySelectorAll('.btn-detalle-evento').forEach((btn) => {
    btn.addEventListener('click', () => {
      const eventoId = btn.dataset.id;
      const evento = eventos.find((item) => String(item.id) === String(eventoId));
      if (evento) abrirDetalleEvento(evento);
    });
  });

  detalle.querySelectorAll('.btn-editar-evento').forEach((btn) => {
    btn.addEventListener('click', () => {
      const eventoId = btn.dataset.id;
      const evento = eventos.find((item) => String(item.id) === String(eventoId));
      if (evento) openEventoModal(evento);
    });
  });

  detalle.querySelectorAll('.btn-eliminar-evento').forEach((btn) => {
    btn.addEventListener('click', () => {
      eliminarEvento(btn.dataset.id);
    });
  });
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
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary py-3">No hay veterinarios registrados.</td></tr>';
    return;
  }
  tbody.innerHTML = VETERINARIOS.map((vet) => `
    <tr>
      <td>${vet.nombre_completo}</td>
      <td>${vet.correo_electronico || '-'}</td>
      <td>${vet.telefono || '-'}</td>
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
      <td>#${diag.caravana}</td>
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
        <p><strong>DNI:</strong> ${veterinario.dni || '-'}</p>
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
    dni: veterinario.dni || '',
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
  document.getElementById('v-dni').value = '';
  document.getElementById('v-nombre').value = '';
  document.getElementById('v-apellido').value = '';
  document.getElementById('v-correo').value = '';
  document.getElementById('v-telefono').value = '';
  document.getElementById('v-fecha-nacimiento').value = '';
}

function getSelectedAnimalIds() {
  return Array.from(seleccionAnimalesEvento).filter(Boolean);
}

function renderSelectedAnimales() {
  const contenedor = document.getElementById('seleccion-animales-evento');
  const contador = document.getElementById('contador-animales-seleccionados');
  const selected = ANIMALES.filter((a) => seleccionAnimalesEvento.has(String(a.id)));
  contenedor.innerHTML = selected.length
    ? selected.map((a) => `
        <span class="badge bg-primary text-white d-inline-flex align-items-center" style="min-width: 180px;">
          #${escapeHtml(a.caravana)} ${escapeHtml(a.nombre || 'S/N')} ${a.categoria ? `(${escapeHtml(a.categoria)})` : ''}
        </span>`).join('')
    : '<span class="text-secondary">No hay animales seleccionados.</span>';
  if (contador) {
    const texto = selected.length === 1 ? '1 seleccionado' : `${selected.length} seleccionados`;
    contador.textContent = texto;
  }
}

function renderAnimalTipoOptions() {
  const tipos = ['Bovino', 'Ovino', 'Porcino'];
  const options = [{ value: '', label: 'Todos los tipos' }, ...tipos.map((tipo) => ({ value: tipo, label: tipo }))];
  setOptions(document.getElementById('s-animal-tipo'), options, false);
}

function renderAnimalSelectionTable() {
  const filter = document.getElementById('s-animal-search').value.trim().toLowerCase();
  const tipo = document.getElementById('s-animal-tipo').value;
  const categoria = document.getElementById('s-animal-categoria').value;

  const rows = ANIMALES
    .filter((a) => {
      const text = `${a.caravana} ${a.nombre || ''} ${a.tipo_animal || ''} ${a.categoria || ''}`.toLowerCase();
      const matchFilter = !filter || text.includes(filter);
      const matchTipo = !tipo || a.tipo_animal === tipo;
      const matchCategoria = !categoria || a.categoria === categoria;
      return matchFilter && matchTipo && matchCategoria;
    })
    .sort((a, b) => String(a.caravana).localeCompare(String(b.caravana), undefined, { numeric: true }))
    .map((a) => {
      const esBloqueado = diagnosticoBloqueo !== null && String(a.id) !== String(diagnosticoBloqueo);
      const checked = seleccionAnimalesEvento.has(String(a.id));
      return `
      <tr>
        <td><input type="checkbox" class="form-check-input evento-animal-checkbox" value="${a.id}" ${checked ? 'checked' : ''} ${esBloqueado ? 'disabled' : ''}></td>
        <td>#${a.caravana}</td>
        <td>${a.nombre || 'S/N'}</td>
        <td>${a.tipo_animal || '-'}</td>
        <td>${a.categoria || '-'}</td>
      </tr>`;
    })
    .join('');

  document.getElementById('tabla-animales-evento').innerHTML = rows || '<tr><td colspan="5" class="text-center text-secondary">No se encontraron animales.</td></tr>';
  document.querySelectorAll('.evento-animal-checkbox').forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const id = String(checkbox.value);
      if (checkbox.checked) seleccionAnimalesEvento.add(id);
      else seleccionAnimalesEvento.delete(id);
      renderSelectedAnimales();
    });
  });
  renderSelectedAnimales();
  updateAnimalLockUI();
}

function updateAnimalLockUI() {
  const bloqueado = diagnosticoBloqueo !== null;
  const search = document.getElementById('s-animal-search');
  const tipo = document.getElementById('s-animal-tipo');
  const categoria = document.getElementById('s-animal-categoria');
  const selectAll = document.getElementById('s-animal-select-all');
  const hint = document.getElementById('evento-animales-hint');
  if (search) search.disabled = bloqueado;
  if (tipo) tipo.disabled = bloqueado;
  if (categoria) categoria.disabled = bloqueado;
  if (selectAll) selectAll.disabled = bloqueado;
  if (hint) {
    hint.textContent = bloqueado
      ? 'El animal se fija automáticamente según el diagnóstico seleccionado.'
      : 'Seleccioná uno o varios animales para el mismo evento.';
  }
}

function renderDiagnosticoInfo() {
  const info = document.getElementById('diagnostico-info');
  if (!info) return;
  const diagnosticoId = document.getElementById('s-diagnostico').value;
  const diagnostico = DIAGNOSTICOS.find((d) => String(d.id) === String(diagnosticoId));
  if (diagnostico) {
    document.getElementById('diag-info-animal').textContent = `#${diagnostico.caravana}`;
    document.getElementById('diag-info-enfermedad').textContent = diagnostico.enfermedad;
    document.getElementById('diag-info-fecha').textContent = formatFecha(diagnostico.fecha_deteccion);
    info.classList.remove('d-none');
  } else {
    info.classList.add('d-none');
  }
}

function aplicarBloqueoDiagnostico({ limpiarAlDesbloquear = true } = {}) {
  const diagnosticoId = document.getElementById('s-diagnostico').value;
  const diagnostico = DIAGNOSTICOS.find((d) => String(d.id) === String(diagnosticoId));
  if (diagnostico && diagnostico.animal_id) {
    diagnosticoBloqueo = String(diagnostico.animal_id);
    seleccionAnimalesEvento = new Set([String(diagnostico.animal_id)]);
  } else {
    const estabaBloqueado = diagnosticoBloqueo !== null;
    diagnosticoBloqueo = null;
    if (estabaBloqueado && limpiarAlDesbloquear) {
      seleccionAnimalesEvento = new Set();
    }
  }
  renderDiagnosticoInfo();
  renderAnimalSelectionTable();
}

function renderAnimalOptions(select, filter = '', selectedIds = []) {
  const normalizedFilter = filter.trim().toLowerCase();
  const selectedValues = selectedIds.map(String);
  const options = ANIMALES
    .filter((a) => {
      const text = `${a.caravana} ${a.nombre || ''} ${a.tipo_animal || ''} ${a.categoria || ''}`.toLowerCase();
      return !normalizedFilter || text.includes(normalizedFilter);
    })
    .sort((a, b) => String(a.caravana).localeCompare(String(b.caravana), undefined, { numeric: true }))
    .map((a) => ({
      value: a.id,
      label: `#${a.caravana} - ${a.nombre || 'S/N'}${a.categoria ? ` (${a.categoria})` : a.tipo_animal ? ` - ${a.tipo_animal}` : ''}`,
      selected: selectedValues.includes(String(a.id)),
    }));
  if (!options.length) {
    select.innerHTML = '<option value="">No se encontraron animales</option>';
    return;
  }
  setOptions(select, options, false);
}

function renderVeterinarioOptions(select, filter = '') {
  const normalizedFilter = filter.trim().toLowerCase();
  const options = VETERINARIOS
    .filter((v) => !normalizedFilter || v.nombre_completo.toLowerCase().includes(normalizedFilter))
    .sort((a, b) => a.nombre_completo.localeCompare(b.nombre_completo, 'es'))
    .map((v) => ({ value: v.id, label: v.nombre_completo }));
  if (!options.length) {
    select.innerHTML = '<option value="">No se encontraron veterinarios</option>';
    return;
  }
  setOptions(select, [{ value: '', label: 'Sin veterinario' }, ...options], false);
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
    document.getElementById('v-dni').value = veterinario.dni || '';
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
  renderFiltros();
}

async function guardarVeterinario() {
  const id = document.getElementById('veterinario-id').value;
  const dni = document.getElementById('v-dni').value.trim();
  const nombre = document.getElementById('v-nombre').value.trim();
  const apellido = document.getElementById('v-apellido').value.trim();
  const correo_electronico = document.getElementById('v-correo').value.trim();
  const telefono = document.getElementById('v-telefono').value.trim();
  const fecha_nacimiento = document.getElementById('v-fecha-nacimiento').value;

  if (!nombre) {
    alert('El nombre es obligatorio.');
    return;
  }

  if (dni && (dni.length < 7 || dni.length > 8)) {
    alert('El DNI debe tener entre 7 y 8 caracteres.');
    return;
  }

  const url = id ? `/api/sanidad/veterinarios/${id}/` : '/api/sanidad/veterinarios/';
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: buildVeterinarioFormData({ dni, nombre, apellido, correo_electronico, telefono, fecha_nacimiento }),
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
  renderFiltros();
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
  renderVeterinarioOptions(document.getElementById('s-veterinario'));

  const diagnosticoOptions = [{ value: '', label: 'Sin diagnóstico' }, ...DIAGNOSTICOS
    .filter((d) => d.estado_actual !== 'Curado')
    .map((d) => ({ value: d.id, label: `#${d.caravana} - ${d.enfermedad} - ${formatFecha(d.fecha_deteccion)}` }))];
  setOptions(document.getElementById('s-diagnostico'), diagnosticoOptions, false);

  renderAnimalTipoOptions();
  renderAnimalSelectionTable();
  renderInsumoOptions();
  renderLoteOptions();
}

function renderLoteOptions() {
  const tipoEvento = document.getElementById('s-tipo').value;
  const selectLote = document.getElementById('s-lote');
  const insumoId = document.getElementById('s-insumo').value;
  const currentValue = String(selectLote.value || '');

  const showOnlyVacuna = tipoEvento === 'Vacunación';
  const loteFilter = (lote) => {
    if (!lote.insumo_tipo) return false;
    if (showOnlyVacuna) {
      return lote.insumo_tipo === 'Vacuna';
    }
    return lote.insumo_tipo !== 'Vacuna' && lote.insumo_tipo !== 'Alimento';
  };

  const filtered = LOTES.filter(loteFilter);
  let matchingLotes = insumoId ? filtered.filter((l) => String(l.insumo_id) === insumoId) : [];

  if (currentValue && !matchingLotes.some((lote) => String(lote.id) === currentValue)) {
    const loteActual = LOTES.find((lote) => String(lote.id) === currentValue);
    if (loteActual) {
      matchingLotes = [loteActual, ...matchingLotes];
    }
  }

  const loteOptions = [{ value: '', label: insumoId ? 'Sin lote disponible' : 'Seleccioná primero un insumo' }, ...matchingLotes.map((l) => ({ value: l.id, label: `${l.nombre} — ${l.insumo_nombre} (${l.stock} u)` }))];
  setOptions(selectLote, loteOptions, false);
  if (currentValue) {
    selectLote.value = currentValue;
  }
  updateStockWarning();
}

function renderInsumoOptions() {
  const tipoEvento = document.getElementById('s-tipo').value;
  const filtroTexto = document.getElementById('s-insumo-search').value.trim().toLowerCase();
  const selectInsumo = document.getElementById('s-insumo');
  const currentValue = String(selectInsumo.value || '');
  const showOnlyVacuna = tipoEvento === 'Vacunación';
  let insumoOptions = [{ value: '', label: 'Sin insumo' }, ...INSUMOS
    .filter((i) => {
      const text = `${i.nombre || ''} ${i.tipo || ''}`.toLowerCase();
      if (filtroTexto && !text.includes(filtroTexto)) return false;
      if (showOnlyVacuna) return i.tipo === 'Vacuna';
      return i.tipo !== 'Vacuna' && i.tipo !== 'Alimento';
    })
    .map((i) => ({ value: i.id, label: `${i.nombre} (${i.tipo})` }))];

  if (currentValue && !insumoOptions.some((option) => String(option.value) === currentValue)) {
    insumoOptions = [{ value: currentValue, label: 'Insumo actual' }, ...insumoOptions];
  }

  setOptions(selectInsumo, insumoOptions, false);
  if (currentValue) {
    selectInsumo.value = currentValue;
  }
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
  document.getElementById('s-animal-tipo').value = '';
  document.getElementById('s-animal-categoria').value = '';
  document.getElementById('s-animal-categoria').classList.add('d-none');
  seleccionAnimalesEvento.clear();
  diagnosticoBloqueo = null;
  renderAnimalSelectionTable();
  document.getElementById('s-veterinario').value = '';
  document.getElementById('s-diagnostico').value = '';
  renderDiagnosticoInfo();
  document.getElementById('s-insumo-search').value = '';
  document.getElementById('s-insumo').value = '';
  renderInsumoOptions();
  renderLoteOptions();
  document.getElementById('s-lote').value = '';
  document.getElementById('i-cantidad').value = '';
  document.getElementById('i-costo').value = '';
  document.getElementById('t-detalle').value = '';
  updateStockWarning();
  updateEstadoByFecha();
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
    seleccionAnimalesEvento = new Set((evento.animal_ids || []).map(String));
    document.getElementById('s-animal-tipo').value = '';
    document.getElementById('s-animal-categoria').value = '';
    document.getElementById('s-animal-categoria').classList.add('d-none');
    renderAnimalSelectionTable();
    document.getElementById('s-veterinario').value = evento.veterinario_id || '';
    document.getElementById('s-diagnostico').value = evento.diagnostico_id || '';
    aplicarBloqueoDiagnostico({ limpiarAlDesbloquear: false });
    renderInsumoOptions();
    document.getElementById('s-insumo').value = evento.lote_insumo_id || '';
    renderLoteOptions();
    document.getElementById('s-lote').value = evento.lote_id || '';
    document.getElementById('i-cantidad').value = evento.cantidad || '';
    document.getElementById('i-costo').value = evento.costo_total || '';
    document.getElementById('t-detalle').value = evento.detalle || '';
    updateStockWarning();
    updateEstadoByFecha();
  }

  modalRegistrarEvento.show();
}

function changeCalendarMonth(offset) {
  const mesSelector = document.getElementById('calendario-mes');
  const [year, month] = mesSelector.value.split('-').map(Number);
  const nuevaFecha = new Date(year, month - 1 + offset, 1);
  mesSelector.value = `${nuevaFecha.getFullYear()}-${String(nuevaFecha.getMonth() + 1).padStart(2, '0')}`;
  renderCalendar();
}

function abrirDetalleEvento(evento) {
  const animales = Array.isArray(evento.animales) ? evento.animales : [];
  const caravanaText = animales.length
    ? animales.map((a) => `#${a.caravana}`).join(', ')
    : evento.caravana;
  const animalText = animales.length
    ? animales.map((a) => `#${a.caravana} ${a.nombre}`).join(', ')
    : evento.animal;
  const warningEl = document.getElementById('detalle-stock-warning');
  const lote = LOTES.find((item) => String(item.id) === String(evento.lote_id)) || null;
  const cantidad = parseFloat(evento.cantidad || 0);

  document.getElementById('detalle-caravana').textContent = caravanaText;
  document.getElementById('detalle-animal').textContent = animalText;
  document.getElementById('detalle-tipo').textContent = evento.tipo;
  document.getElementById('detalle-estado').textContent = evento.estado ? 'Aplicado' : 'Pendiente';
  document.getElementById('detalle-fecha').textContent = formatFecha(evento.fecha_aplicacion);
  document.getElementById('detalle-veterinario').textContent = evento.veterinario;
  document.getElementById('detalle-diagnostico').textContent = evento.diagnostico;
  document.getElementById('detalle-lote').textContent = evento.lote;
  document.getElementById('detalle-cantidad').textContent = evento.cantidad || '-';
  document.getElementById('detalle-costo').textContent = evento.costo_total || '-';
  document.getElementById('detalle-observaciones').textContent = evento.detalle || '-';

  if (warningEl) {
    if (lote && !Number.isNaN(cantidad) && cantidad > 0 && Number(cantidad) > Number(lote.stock || 0)) {
      warningEl.textContent = `Stock insuficiente: el lote seleccionado tiene solo ${lote.stock} unidad${lote.stock === 1 ? '' : 'es'} disponibles.`;
      warningEl.classList.remove('d-none');
    } else {
      warningEl.textContent = '';
      warningEl.classList.add('d-none');
    }
  }

  const modal = new bootstrap.Modal(document.getElementById('modalDetalleEvento'));
  modal.show();
}

async function guardarEvento() {
  const id = document.getElementById('evento-id').value;
  const tipo = document.getElementById('s-tipo').value;
  const fecha_aplicacion = document.getElementById('d-fecha').value;
  const estado = parseBoolean(document.getElementById('s-estado').value);
  const animalIds = Array.from(seleccionAnimalesEvento).filter(Boolean);
  const veterinarioId = document.getElementById('s-veterinario').value;
  const diagnosticoId = document.getElementById('s-diagnostico').value;
  const loteId = document.getElementById('s-lote').value;
  const cantidad = document.getElementById('i-cantidad').value;
  const costo_total = document.getElementById('i-costo').value;
  const detalle = document.getElementById('t-detalle').value;

  if (!tipo || !fecha_aplicacion || !animalIds.length) {
    alert('Debe completar tipo, fecha y al menos un animal.');
    return;
  }
  if (new Date(fecha_aplicacion) > new Date(new Date().toISOString().split('T')[0])) {
    document.getElementById('s-estado').value = 'false';
  }

  const fechaEvento = new Date(fecha_aplicacion);
  const hoy = new Date(new Date().toISOString().split('T')[0]);
  const estadoAuto = fechaEvento > hoy ? false : estado;

  const eventoNuevo = {
    id,
    detalle,
    tipo,
    fecha_aplicacion,
    estado: estadoAuto,
    costo_total: costo_total || '0',
    animal_ids: animalIds,
    veterinario_id: veterinarioId || null,
    diagnostico_id: diagnosticoId || null,
    lote_id: loteId || null,
    cantidad: cantidad || '',
  };

  if (guardandoEvento) {
    return;
  }
  guardandoEvento = true;
  const btnGuardar = document.getElementById('btn-guardar-evento');
  btnGuardar.disabled = true;
  const originalBtnText = btnGuardar.textContent;
  btnGuardar.textContent = 'Guardando...';

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
    renderCalendar();
    if (fechaSeleccionada) showCalendarDetails(fechaSeleccionada);
    const modal = bootstrap.Modal.getInstance(document.getElementById('modalRegistrarEvento'));
    if (modal) modal.hide();
  } catch (error) {
    alert(error.message);
  } finally {
    guardandoEvento = false;
    btnGuardar.disabled = false;
    btnGuardar.textContent = originalBtnText;
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
    renderCalendar();
    if (fechaSeleccionada) showCalendarDetails(fechaSeleccionada);
  } catch (error) {
    alert(error.message);
  }
}

function handleTablaBodyClick(event) {
  const button = event.target.closest('button');
  if (!button) return;
  const id = button.dataset.id;
  if (!id) return;

  if (button.classList.contains('btn-detalle-evento')) {
    const evento = EVENTOS.find((item) => String(item.id) === id);
    if (evento) abrirDetalleEvento(evento);
    return;
  }

  if (button.classList.contains('btn-editar-evento')) {
    const evento = EVENTOS.find((item) => String(item.id) === id);
    if (evento) openEventoModal(evento);
    return;
  }

  if (button.classList.contains('btn-eliminar-evento')) {
    eliminarEvento(id);
    return;
  }
}

function bindEventosTabla() {
  // Ya no se usa delegación directa para los botones de tabla.
}

function setupListeners() {
  if (window.sanidadListenersSetup) return;
  window.sanidadListenersSetup = true;

  document.getElementById('form-evento').addEventListener('submit', (event) => {
    event.preventDefault();
    guardarEvento();
  });
  document.getElementById('btn-guardar-evento').addEventListener('click', guardarEvento);
  document.getElementById('btn-registrar-evento').addEventListener('click', () => openEventoModal());
  document.getElementById('btn-registrar-enfermedad').addEventListener('click', () => openEnfermedadModal());
  document.getElementById('btn-registrar-diagnostico').addEventListener('click', () => openDiagnosticoModal());
  document.getElementById('btn-registrar-veterinario').addEventListener('click', () => openVeterinarioModal());
  document.getElementById('d-animal-search').addEventListener('input', (event) => renderAnimalOptions(document.getElementById('d-animal'), event.target.value));
  document.getElementById('s-animal-search').addEventListener('input', () => renderAnimalSelectionTable());
  document.getElementById('s-animal-tipo').addEventListener('change', () => {
    const categoriaSelect = document.getElementById('s-animal-categoria');
    if (document.getElementById('s-animal-tipo').value === 'Bovino') {
      categoriaSelect.classList.remove('d-none');
    } else {
      categoriaSelect.classList.add('d-none');
      categoriaSelect.value = '';
    }
    renderAnimalSelectionTable();
  });
  document.getElementById('s-animal-categoria').addEventListener('change', renderAnimalSelectionTable);
  document.getElementById('s-tipo').addEventListener('change', () => {
    renderInsumoOptions();
    renderLoteOptions();
  });
  document.getElementById('s-insumo-search').addEventListener('input', () => {
    renderInsumoOptions();
    renderLoteOptions();
  });
  document.getElementById('s-insumo').addEventListener('change', renderLoteOptions);
  document.getElementById('s-lote').addEventListener('change', updateStockWarning);
  document.getElementById('i-cantidad').addEventListener('input', updateStockWarning);
  document.getElementById('d-fecha').addEventListener('change', updateEstadoByFecha);
  document.getElementById('s-animal-select-all').addEventListener('click', () => {
    if (diagnosticoBloqueo !== null) return;
    const checkboxes = Array.from(document.querySelectorAll('#tabla-animales-evento .evento-animal-checkbox'));
    const visibleIds = checkboxes.map((checkbox) => String(checkbox.value));
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => seleccionAnimalesEvento.has(id));
    visibleIds.forEach((id) => {
      if (allSelected) seleccionAnimalesEvento.delete(id);
      else seleccionAnimalesEvento.add(id);
    });
    renderAnimalSelectionTable();
  });
  document.getElementById('s-veterinario-search').addEventListener('input', (event) => renderVeterinarioOptions(document.getElementById('s-veterinario'), event.target.value));
  document.getElementById('s-diagnostico').addEventListener('change', aplicarBloqueoDiagnostico);
  document.getElementById('btn-vista-calendario').addEventListener('click', () => toggleVista('calendario'));
  document.getElementById('btn-vista-lista').addEventListener('click', () => toggleVista('lista'));
  document.getElementById('btn-cal-prev').addEventListener('click', () => changeCalendarMonth(-1));
  document.getElementById('btn-cal-next').addEventListener('click', () => changeCalendarMonth(1));
  document.getElementById('calendario-mes').addEventListener('change', () => {
    renderCalendar();
  });

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
    renderCalendar();
  });
  document.getElementById('tabla-sanidad-body').addEventListener('click', handleTablaBodyClick);
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
