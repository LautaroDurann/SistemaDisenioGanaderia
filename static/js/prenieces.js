(() => {
  'use strict';

  const data = window.GANASTOCK_DATA || {};

  let PRENIECES = data.prenieces || [];
  let PARTOS = data.partos || [];
  let EVENTOS = data.eventos_inseminacion || [];
  let MADRES = data.madres || [];
  let PADRES = data.padres || [];
  let VETERINARIOS = data.veterinarios || [];
  let KPIS = data.kpis || {};

  const TIPOS = data.tipos || ['Natural', 'Inseminación'];
  const ESTADOS = data.estados || ['Preñada', 'A confirmar', 'Vacía'];
  const ESPECIES = data.especies || ['Bovino', 'Porcino', 'Ovino'];
  const MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const ESTADO_BADGE = {
    'Preñada': 'text-bg-success',
    'A confirmar': 'text-bg-warning',
    'Vacía': 'text-bg-secondary',
  };
  const FILAS_POR_PAGINA = 5;
  let paginaActual = 1;
  let paginaPartosActual = 1;
  let paginaInsemActual = 1;

  const $ = (id) => document.getElementById(id);
  const csrf = () => document.cookie.split('; ').find((v) => v.startsWith('csrftoken='))?.split('=')[1] || '';
  const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[c]));
  const fmtFecha = (iso) => {
    if (!iso) return '-';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
  };
  const dinero = (v) => (v ? `$ ${Number(v).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '-');
  const hoyInicio = () => { const h = new Date(); h.setHours(0, 0, 0, 0); return h; };

  function sumarMeses(fecha, meses) {
    const d = new Date(fecha.getTime());
    const mes = d.getMonth() + meses;
    const anio = d.getFullYear() + Math.floor(mes / 12);
    const m = ((mes % 12) + 12) % 12;
    const ultimoDia = new Date(anio, m + 1, 0).getDate();
    d.setDate(Math.min(d.getDate(), ultimoDia));
    d.setMonth(m);
    d.setFullYear(anio);
    return d;
  }

  function estimarParto(tipoAnimal, fechaIso) {
    const f = new Date(`${fechaIso}T00:00:00`);
    if (Number.isNaN(f.getTime())) return null;
    if (tipoAnimal === 'Porcino') return new Date(sumarMeses(f, 3).getTime() + 21 * 86400000);
    return sumarMeses(f, tipoAnimal === 'Ovino' ? 5 : 9);
  }

  function mesSemana(fecha) {
    if (!fecha) return '-';
    return `${MESES[fecha.getMonth() + 1]} · Semana ${Math.floor((fecha.getDate() - 1) / 7) + 1}`;
  }

  function faltante(fecha) {
    if (!fecha) return '-';
    const dias = Math.round((fecha - hoyInicio()) / 86400000);
    if (dias < 0) return 'Vencido';
    if (dias >= 30) {
      const meses = Math.floor(dias / 30);
      const semanas = Math.floor((dias % 30) / 7);
      return `${meses} meses y ${semanas} semanas`;
    }
    const semanas = Math.floor(dias / 7);
    return `${semanas} semanas y ${dias % 7} días`;
  }

  function renderKpis() {
    $('kpi-partos-anio').textContent = KPIS.partos_anio || 0;
    $('kpi-vacas-preniadas').textContent = KPIS.vacas_preniadas || 0;
    $('kpi-total-prenieces').textContent = PRENIECES.length;
    $('kpi-proximo-parto').textContent = KPIS.proximo_parto || '-';
    $('kpi-proximo-parto-animal').textContent = KPIS.proximo_parto_animal || 'Próximo parto estimado';
  }

  function recomputarKpis() {
    const anio = hoyInicio().getFullYear();
    const partosAnio = PRENIECES.filter((p) => p.parto_fecha && Number(p.parto_fecha.slice(0, 4)) === anio).length;
    const preniadas = PRENIECES.filter((p) => p.estado_actual === 'Preñada' && !p.parto_id);

    let proxima = null;
    preniadas.forEach((p) => {
      if (!p.fecha_estimada) return;
      if (!proxima || p.fecha_estimada < proxima.fecha_estimada) proxima = p;
    });

    KPIS = {
      partos_anio: partosAnio,
      vacas_preniadas: preniadas.length,
      proximo_parto: proxima ? fmtFecha(proxima.fecha_estimada) : '-',
      proximo_parto_animal: proxima
        ? `${proxima.madre_nombre} #${proxima.madre_caravana} · en ${Math.max(0, Math.round((new Date(`${proxima.fecha_estimada}T00:00:00`) - hoyInicio()) / 86400000))} días`
        : '-',
    };
    renderKpis();
  }

  function actualizarMadresPreniadas() {
    const preniadas = new Set(
      PRENIECES.filter((p) => p.estado_actual === 'Preñada' && !p.parto_id).map((p) => p.madre_id),
    );
    MADRES = MADRES.map((m) => ({ ...m, preniada: preniadas.has(m.id) }));
  }

  function aplicarFiltros() {
    const buscar = $('f-buscar').value.trim().toLowerCase();
    const especie = $('f-especie').value;
    const tipo = $('f-tipo').value;
    const estado = $('f-estado').value;
    return PRENIECES.filter((p) => {
      const hayBusqueda = `${p.madre_caravana} ${p.madre_nombre} ${p.padre} ${p.detalle}`.toLowerCase();
      return (!buscar || hayBusqueda.includes(buscar))
        && (!especie || p.madre_tipo === especie)
        && (!tipo || p.tipo === tipo)
        && (!estado || p.estado_actual === estado);
    });
  }

  function renderTabla() {
    const datos = aplicarFiltros();
    const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
    if (paginaActual > totalPaginas) paginaActual = totalPaginas;
    const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
    const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

    $('tabla-prenieces-body').innerHTML = pagina.map((p) => {
      const estado = p.parto_id ? 'Parida' : p.estado_actual;
      const badge = p.parto_id ? 'text-bg-primary' : (ESTADO_BADGE[p.estado_actual] || 'text-bg-secondary');
      const partoCell = p.parto_id
        ? `${fmtFecha(p.parto_fecha)} <span class="badge ${p.parto_vivo ? 'text-bg-success' : 'text-bg-danger'}">${p.parto_vivo ? 'Vivo' : 'Muerto'}</span>`
        : '<span class="text-secondary">—</span>';
      const acciones = `
        <button class="btn btn-sm btn-outline-secondary btn-ver" data-id="${p.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
        ${p.parto_id ? '' : `<button class="btn btn-sm btn-outline-success btn-finalizar" data-id="${p.id}" title="Finalizar preñez · cargar parto"><i class="bi bi-check2-circle"></i></button>`}
        <button class="btn btn-sm btn-outline-primary btn-editar" data-id="${p.id}" title="Editar preñez"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger btn-eliminar" data-id="${p.id}" title="Eliminar preñez"><i class="bi bi-trash"></i></button>`;
      return `
        <tr>
          <td>
            <div class="fw-semibold">#${escapeHtml(p.madre_caravana)} ${escapeHtml(p.madre_nombre)}</div>
            <small class="text-secondary">${escapeHtml(p.madre_parcela)}</small>
          </td>
          <td>${escapeHtml(p.tipo)}</td>
          <td>${fmtFecha(p.fecha)}</td>
          <td><span class="badge ${badge}">${estado}</span></td>
          <td>
            <div>${fmtFecha(p.fecha_estimada)}</div>
            <small class="text-success">${escapeHtml(p.mes_semana_parto)}</small>
          </td>
          <td>${p.parto_id ? '<span class="text-secondary">—</span>' : `<span class="badge text-bg-light border">${escapeHtml(p.faltante_parto)}</span>`}</td>
          <td>${partoCell}</td>
          <td class="text-end">${acciones}</td>
        </tr>`;
    }).join('') || '<tr><td colspan="8" class="text-center text-secondary py-4">Todavía no hay preñeces registradas.</td></tr>';

    $('tabla-info').textContent = datos.length
      ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} preñeces`
      : 'Sin resultados para los filtros aplicados';

    const paginacion = $('tabla-paginacion');
    paginacion.innerHTML = Array.from({ length: totalPaginas }, (_, i) => i + 1)
      .map((np) => `<li class="page-item ${np === paginaActual ? 'active' : ''}"><button class="page-link" data-pagina="${np}">${np}</button></li>`)
      .join('');
    paginacion.querySelectorAll('[data-pagina]').forEach((btn) => {
      btn.addEventListener('click', () => {
        paginaActual = parseInt(btn.dataset.pagina, 10);
        renderTabla();
      });
    });

    document.querySelectorAll('.btn-ver').forEach((btn) => {
      btn.addEventListener('click', () => verPreniez(PRENIECES.find((x) => String(x.id) === String(btn.dataset.id))));
    });
    document.querySelectorAll('.btn-finalizar').forEach((btn) => {
      btn.addEventListener('click', () => abrirModalParto(PRENIECES.find((x) => String(x.id) === String(btn.dataset.id))));
    });
    document.querySelectorAll('.btn-editar').forEach((btn) => {
      btn.addEventListener('click', () => abrirEdicion(PRENIECES.find((x) => String(x.id) === String(btn.dataset.id))));
    });
    document.querySelectorAll('.btn-eliminar').forEach((btn) => {
      btn.addEventListener('click', () => eliminarPreniez(Number(btn.dataset.id)));
    });
  }

  function aplicarFiltrosPartos() {
    const buscar = $('f-parto-buscar').value.trim().toLowerCase();
    const vivo = $('f-parto-estado').value;
    const especie = $('f-parto-especie').value;
    return PARTOS.filter((pt) => {
      const hayBusqueda = `${pt.madre_caravana} ${pt.madre_nombre} ${pt.crias.map((c) => c.nombre).join(' ')}`.toLowerCase();
      return (!buscar || hayBusqueda.includes(buscar))
        && (!vivo || String(pt.vivo) === vivo)
        && (!especie || pt.madre_tipo === especie);
    });
  }

  function renderPartos() {
    $('partos-count').textContent = PARTOS.length;
    const datos = aplicarFiltrosPartos();
    const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
    if (paginaPartosActual > totalPaginas) paginaPartosActual = totalPaginas;
    const inicio = (paginaPartosActual - 1) * FILAS_POR_PAGINA;
    const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

    $('tabla-partos-body').innerHTML = pagina.map((pt) => `
      <tr>
        <td>${fmtFecha(pt.fecha)}</td>
        <td>
          <div class="fw-semibold">#${escapeHtml(pt.madre_caravana)} ${escapeHtml(pt.madre_nombre)}</div>
        </td>
        <td>${escapeHtml(pt.madre_tipo || '-')}</td>
        <td>${escapeHtml(pt.tipo_preñez || '-')}</td>
        <td><span class="badge ${pt.vivo ? 'text-bg-success' : 'text-bg-danger'}">${pt.vivo ? 'Vivo' : 'Muerto'}</span></td>
        <td>${pt.crias && pt.crias.length
          ? pt.crias.map((c) => `<span class="badge text-bg-light border me-1">#${escapeHtml(c.caravana)} ${escapeHtml(c.nombre)} · ${c.sexo}</span>`).join('')
          : '<span class="text-secondary">Sin crías</span>'}</td>
      </tr>`).join('') || '<tr><td colspan="6" class="text-center text-secondary py-4">Todavía no hay partos registrados.</td></tr>';

    $('partos-info').textContent = datos.length
      ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} partos`
      : 'Sin resultados para los filtros aplicados';

    const paginacion = $('partos-paginacion');
    paginacion.innerHTML = Array.from({ length: totalPaginas }, (_, i) => i + 1)
      .map((np) => `<li class="page-item ${np === paginaPartosActual ? 'active' : ''}"><button class="page-link" data-pagina="${np}">${np}</button></li>`)
      .join('');
    paginacion.querySelectorAll('[data-pagina]').forEach((btn) => {
      btn.addEventListener('click', () => {
        paginaPartosActual = parseInt(btn.dataset.pagina, 10);
        renderPartos();
      });
    });
  }

  function aplicarFiltrosInsem() {
    const buscar = $('f-insem-buscar').value.trim().toLowerCase();
    const estado = $('f-insem-estado').value;
    const padre = $('f-insem-padre').value;
    return EVENTOS.filter((e) => {
      const texto = `${e.padre} ${e.animales.map((a) => `${a.caravana} ${a.nombre}`).join(' ')}`.toLowerCase();
      return (!buscar || texto.includes(buscar))
        && (!estado || String(e.estado) === estado)
        && (!padre || String(e.padre_id) === padre);
    });
  }

  function renderInseminaciones() {
    $('insem-count').textContent = EVENTOS.length;
    const datos = aplicarFiltrosInsem();
    const totalPaginas = Math.max(1, Math.ceil(datos.length / FILAS_POR_PAGINA));
    if (paginaInsemActual > totalPaginas) paginaInsemActual = totalPaginas;
    const inicio = (paginaInsemActual - 1) * FILAS_POR_PAGINA;
    const pagina = datos.slice(inicio, inicio + FILAS_POR_PAGINA);

    $('tabla-inseminaciones-body').innerHTML = pagina.map((e) => `
      <tr>
        <td>${fmtFecha(e.fecha_aplicacion)}</td>
        <td><span class="badge ${e.estado ? 'text-bg-success' : 'text-bg-warning'}">${e.estado ? 'Aplicada' : 'Programada'}</span></td>
        <td>${escapeHtml(e.padre)}</td>
        <td>
          <span class="fw-semibold">${e.preñadas}/${e.total_hembras}</span>
          <small class="text-secondary d-block">${e.animales.map((a) => `<span class="badge text-bg-light border me-1">#${escapeHtml(a.caravana)} ${escapeHtml(a.nombre)}</span>`).join('')}</small>
        </td>
        <td>${dinero(e.costo_total)}</td>
        <td class="text-end text-nowrap">
          <button class="btn btn-sm btn-outline-primary btn-preniadas" data-id="${e.id}" title="Registrar preñadas"><i class="bi bi-clipboard2-heart"></i></button>
          <button class="btn btn-sm btn-outline-secondary btn-insem-editar" data-id="${e.id}" title="Editar inseminación"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger btn-insem-eliminar" data-id="${e.id}" title="Eliminar inseminación"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="6" class="text-center text-secondary py-4">Todavía no hay inseminaciones registradas.</td></tr>';

    $('insem-info').textContent = datos.length
      ? `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, datos.length)} de ${datos.length} inseminaciones`
      : 'Sin resultados para los filtros aplicados';

    const paginacion = $('insem-paginacion');
    paginacion.innerHTML = Array.from({ length: totalPaginas }, (_, i) => i + 1)
      .map((np) => `<li class="page-item ${np === paginaInsemActual ? 'active' : ''}"><button class="page-link" data-pagina="${np}">${np}</button></li>`)
      .join('');
    paginacion.querySelectorAll('[data-pagina]').forEach((btn) => {
      btn.addEventListener('click', () => {
        paginaInsemActual = parseInt(btn.dataset.pagina, 10);
        renderInseminaciones();
      });
    });

    document.querySelectorAll('.btn-preniadas').forEach((btn) => {
      btn.addEventListener('click', () => abrirModalPreniadas(EVENTOS.find((x) => String(x.id) === String(btn.dataset.id))));
    });
    document.querySelectorAll('.btn-insem-editar').forEach((btn) => {
      btn.addEventListener('click', () => abrirEdicionInseminacion(EVENTOS.find((x) => String(x.id) === String(btn.dataset.id))));
    });
    document.querySelectorAll('.btn-insem-eliminar').forEach((btn) => {
      btn.addEventListener('click', () => eliminarInseminacion(Number(btn.dataset.id)));
    });
  }

  function sincronizarEventos() {
    EVENTOS = EVENTOS.map((e) => {
      const animales = e.animales.map((a) => {
        const deEste = PRENIECES.find((p) => p.madre_id === a.id && p.evento_sanitario_id === e.id);
        const activa = PRENIECES.find((p) => p.madre_id === a.id && p.estado_actual === 'Preñada' && !p.parto_id);
        const preniez = deEste || activa;
        return { ...a, preniada: !!preniez, de_este_evento: !!deEste, preniez_id: preniez?.id || null };
      });
      return { ...e, animales, preñadas: animales.filter((a) => a.preniada).length };
    });
  }

  function renderInsemAnimales(search) {
    const termino = (search || '').toLowerCase();
    const seleccionadas = new Set(
      Array.from($('insem-animales').querySelectorAll('input:checked')).map((i) => Number(i.value)),
    );
    const opciones = MADRES.filter((m) => !termino || `#${m.caravana} ${m.nombre} ${m.tipo}`.toLowerCase().includes(termino));
    $('insem-animales').innerHTML = opciones.length
      ? opciones.map((m) => `
        <label class="list-group-item d-flex align-items-center gap-2 py-1">
          <input class="form-check-input m-0 insem-animal-check" type="checkbox" value="${m.id}" ${seleccionadas.has(m.id) ? 'checked' : ''}>
          <span class="flex-grow-1 small">#${escapeHtml(m.caravana)} ${escapeHtml(m.nombre)} <span class="text-secondary">(${m.tipo})</span></span>
          ${m.preniada ? '<span class="badge text-bg-warning">Preñada</span>' : ''}
        </label>`).join('')
      : '<li class="list-group-item text-secondary small">Sin animales hembra disponibles.</li>';
    $('insem-animales-info').textContent = `${seleccionadas.size} hembra(s) seleccionada(s)`;
  }

  function seleccionadasInsem() {
    return Array.from($('insem-animales').querySelectorAll('input:checked')).map((i) => i.value);
  }

  function resetFormInseminacion() {
    $('insem-evento-id').value = '';
    $('modalInseminacionTitle').textContent = 'Agendar Inseminación';
    $('form-inseminacion').reset();
    $('insem-fecha').value = hoyInicio().toISOString().slice(0, 10);
    $('insem-estado').value = 'false';
    $('insem-animales-search').value = '';
    renderInsemAnimales('');
  }

  function abrirEdicionInseminacion(e) {
    if (!e) return;
    $('insem-evento-id').value = e.id;
    $('modalInseminacionTitle').textContent = 'Editar Inseminación';
    $('form-inseminacion').reset();
    $('insem-fecha').value = e.fecha_aplicacion;
    $('insem-estado').value = String(e.estado);
    $('insem-padre').value = e.padre_id || '';
    $('insem-veterinario').value = e.veterinario_id || '';
    $('insem-costo').value = e.costo_total || '';
    $('insem-detalle').value = e.detalle || '';
    $('insem-animales-search').value = '';
    renderInsemAnimales('');
    const ids = new Set(e.animales.map((a) => a.id));
    Array.from($('insem-animales').querySelectorAll('.insem-animal-check')).forEach((chk) => {
      if (ids.has(Number(chk.value))) chk.checked = true;
    });
    $('insem-animales-info').textContent = `${ids.size} hembra(s) seleccionada(s)`;
    bootstrap.Modal.getOrCreateInstance($('modalInseminacion')).show();
  }

  async function guardarInseminacion() {
    const id = $('insem-evento-id').value;
    const formData = new FormData();
    formData.append('fecha_aplicacion', $('insem-fecha').value);
    formData.append('estado', $('insem-estado').value);
    formData.append('padre_id', $('insem-padre').value);
    formData.append('veterinario_id', $('insem-veterinario').value || '');
    formData.append('costo_total', $('insem-costo').value || '');
    formData.append('detalle', $('insem-detalle').value || '');
    seleccionadasInsem().forEach((a) => formData.append('animales', a));
    const response = await fetch(id ? `/api/prenieces/inseminaciones/${id}/` : '/api/prenieces/inseminaciones/', {
      method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: formData,
    });
    const json = await response.json();
    if (!response.ok) {
      alert(json.error || 'No se pudo guardar la inseminación.');
      return;
    }
    EVENTOS = id
      ? EVENTOS.map((x) => (x.id === json.evento.id ? json.evento : x))
      : [json.evento, ...EVENTOS];
    renderInseminaciones();
    bootstrap.Modal.getOrCreateInstance($('modalInseminacion')).hide();
  }

  async function eliminarInseminacion(id) {
    if (!window.confirm('¿Eliminar definitivamente esta inseminación?')) return;
    const response = await fetch(`/api/prenieces/inseminaciones/${id}/eliminar/`, {
      method: 'POST', headers: { 'X-CSRFToken': csrf() },
    });
    const json = await response.json();
    if (!response.ok) {
      alert(json.error || 'No se pudo eliminar la inseminación.');
      return;
    }
    EVENTOS = EVENTOS.filter((x) => x.id !== id);
    renderInseminaciones();
  }

  function abrirModalPreniadas(e) {
    if (!e) return;
    $('preniadas-lista').dataset.eventoId = e.id;
    $('preniadas-info').innerHTML = `Inseminación del <strong>${fmtFecha(e.fecha_aplicacion)}</strong> · Padre: <strong>${escapeHtml(e.padre)}</strong>`;
    $('preniadas-lista').innerHTML = e.animales.map((a) => `
      <label class="list-group-item d-flex align-items-center gap-2 py-1">
        <input class="form-check-input m-0 preniada-check" type="checkbox" value="${a.id}" ${a.preniada ? 'checked disabled' : ''}>
        <span class="flex-grow-1 small">#${escapeHtml(a.caravana)} ${escapeHtml(a.nombre)} <span class="text-secondary">(${a.tipo})</span></span>
        ${a.preniada ? '<span class="badge text-bg-success">Preñada</span>' : ''}
      </label>`).join('') || '<li class="list-group-item text-secondary small">Este evento no tiene hembras asociadas.</li>';
    bootstrap.Modal.getOrCreateInstance($('modalPreniadas')).show();
  }

  async function guardarPreniadas() {
    const eventoId = Number($('preniadas-lista').dataset.eventoId);
    const evento = EVENTOS.find((x) => x.id === eventoId);
    if (!evento) return;
    const seleccionadas = Array.from($('preniadas-lista').querySelectorAll('.preniada-check:checked:not(:disabled)')).map((i) => i.value);
    if (!seleccionadas.length) {
      alert('Marcá al menos una hembra preñada para continuar.');
      return;
    }
    const formData = new FormData();
    seleccionadas.forEach((a) => formData.append('animales', a));
    const response = await fetch(`/api/prenieces/inseminaciones/${evento.id}/preniadas/`, {
      method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: formData,
    });
    const json = await response.json();
    if (!response.ok) {
      alert(json.error || 'No se pudieron registrar las preñadas.');
      return;
    }
    PRENIECES = [...json.prenieces, ...PRENIECES];
    EVENTOS = EVENTOS.map((x) => (x.id === json.evento.id ? json.evento : x));
    actualizarMadresPreniadas();
    recomputarKpis();
    renderTabla();
    renderInseminaciones();
    bootstrap.Modal.getOrCreateInstance($('modalPreniadas')).hide();
  }

  function renderMadresSelect(search) {
    const termino = (search || '').toLowerCase();
    const opciones = MADRES
      .filter((m) => !termino || `#${m.caravana} ${m.nombre} ${m.tipo}`.toLowerCase().includes(termino))
      .map((m) => `<option value="${m.id}" data-tipo="${m.tipo}" data-preniada="${m.preniada}">#${m.caravana} ${m.nombre} (${m.tipo})${m.preniada ? ' — YA PREÑADA' : ''}</option>`)
      .join('');
    $('p-madre').innerHTML = opciones || '<option value="">Sin animales hembra disponibles</option>';
  }

  function actualizarEstimacion() {
    const madre = MADRES.find((m) => String(m.id) === String($('p-madre').value));
    const fecha = estimarParto(madre?.tipo, $('p-fecha').value);
    const bloque = $('preniez-estimacion');
    if (!fecha || !madre) {
      bloque.classList.add('d-none');
      return;
    }
    $('preniez-estimacion-fecha').textContent = fmtFecha(fecha.toISOString().slice(0, 10));
    $('preniez-estimacion-mes').textContent = mesSemana(fecha);
    bloque.classList.remove('d-none');
  }

  function resetFormPreniez() {
    $('preniez-id').value = '';
    $('modalPreniezTitle').textContent = 'Registrar Preñez';
    $('form-preniez').reset();
    renderMadresSelect('');
    $('p-fecha').value = hoyInicio().toISOString().slice(0, 10);
    $('p-tipo').value = TIPOS[0] || 'Natural';
    $('p-estado').value = 'Preñada';
    $('preniez-estimacion').classList.add('d-none');
  }

  function abrirEdicion(p) {
    if (!p) return;
    $('preniez-id').value = p.id;
    $('modalPreniezTitle').textContent = 'Editar Preñez';
    $('form-preniez').reset();
    renderMadresSelect('');
    $('p-madre').value = p.madre_id;
    $('p-padre').value = p.padre_id || '';
    $('p-fecha').value = p.fecha;
    $('p-tipo').value = p.tipo;
    $('p-estado').value = p.estado_actual;
    $('p-detalle').value = p.detalle || '';
    actualizarEstimacion();
    bootstrap.Modal.getOrCreateInstance($('modalPreniez')).show();
  }

  async function guardarPreniez() {
    const id = $('preniez-id').value;
    const formData = new FormData();
    formData.append('madre_id', $('p-madre').value);
    formData.append('padre_id', $('p-padre').value || '');
    formData.append('fecha', $('p-fecha').value);
    formData.append('tipo', $('p-tipo').value);
    formData.append('estado_actual', $('p-estado').value);
    formData.append('detalle', $('p-detalle').value || '');
    const response = await fetch(id ? `/api/prenieces/${id}/` : '/api/prenieces/', {
      method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: formData,
    });
    const json = await response.json();
    if (!response.ok) {
      alert(json.error || 'No se pudo guardar la preñez.');
      return;
    }
    const preniez = json.preniez;
    PRENIECES = id
      ? PRENIECES.map((x) => (x.id === preniez.id ? preniez : x))
      : [preniez, ...PRENIECES];
    if (id) {
      PARTOS = PARTOS.map((pt) => (pt.preniez_id === preniez.id
        ? { ...pt, madre_nombre: preniez.madre_nombre, madre_caravana: preniez.madre_caravana, madre_tipo: preniez.madre_tipo, tipo_preñez: preniez.tipo }
        : pt));
      renderPartos();
    }
    actualizarMadresPreniadas();
    recomputarKpis();
    sincronizarEventos();
    renderTabla();
    renderInseminaciones();
    bootstrap.Modal.getOrCreateInstance($('modalPreniez')).hide();
  }

  function verPreniez(p) {
    if (!p) return;
    $('det-madre').textContent = p.madre_nombre;
    $('det-caravana').textContent = `#${p.madre_caravana}`;
    $('det-especie').textContent = p.madre_tipo;
    $('det-fecha').textContent = fmtFecha(p.fecha);
    $('det-tipo').textContent = p.tipo;
    $('det-estado').textContent = p.parto_id ? 'Parida' : p.estado_actual;
    $('det-padre').textContent = p.padre;
    $('det-evento').textContent = p.evento_sanitario_id
      ? `Evento #${p.evento_sanitario_id} · ${fmtFecha(p.evento_fecha)}`
      : '—';
    $('det-veterinario').textContent = p.evento_veterinario;
    $('det-estimada-fecha').textContent = fmtFecha(p.fecha_estimada);
    $('det-estimada-mes').textContent = p.mes_semana_parto;
    $('det-faltante').textContent = p.parto_id ? '—' : p.faltante_parto;
    $('det-parto').textContent = p.parto_id ? `${fmtFecha(p.parto_fecha)} · ${p.parto_vivo ? 'Nació vivo' : 'Nació muerto'}` : 'Sin registrar';
    $('det-observaciones').textContent = p.detalle || '-';
    $('det-crias').innerHTML = (p.crias && p.crias.length)
      ? p.crias.map((c) => `<span class="badge text-bg-light border me-1 mb-1">#${escapeHtml(c.caravana)} ${escapeHtml(c.nombre)} · ${c.sexo}</span>`).join('')
      : '<span class="text-secondary">Sin crías registradas.</span>';
    bootstrap.Modal.getOrCreateInstance($('modalDetallePreniez')).show();
  }

  function abrirModalParto(p) {
    if (!p) return;
    $('parto-preniez-id').value = p.id;
    $('parto-fecha').value = hoyInicio().toISOString().slice(0, 10);
    $('parto-vivo').checked = true;
    $('parto-madre-info').innerHTML = `Preñez de <strong>#${escapeHtml(p.madre_caravana)} ${escapeHtml(p.madre_nombre)}</strong> · Parto estimado ${fmtFecha(p.fecha_estimada)} <span class="text-success">(${escapeHtml(p.mes_semana_parto)})</span>`;
    bootstrap.Modal.getOrCreateInstance($('modalParto')).show();
  }

  async function guardarParto() {
    const id = $('parto-preniez-id').value;
    if (!id) return;
    const formData = new FormData();
    formData.append('fecha', $('parto-fecha').value);
    formData.append('vivo', $('parto-vivo').checked ? 'true' : 'false');
    const response = await fetch(`/api/prenieces/${id}/finalizar/`, {
      method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: formData,
    });
    const json = await response.json();
    if (!response.ok) {
      alert(json.error || 'No se pudo registrar el parto.');
      return;
    }
    PRENIECES = PRENIECES.map((x) => (x.id === json.preniez.id ? json.preniez : x));
    PARTOS = [{ ...json.parto, crias: [], madre_nombre: json.preniez.madre_nombre, madre_caravana: json.preniez.madre_caravana, madre_tipo: json.preniez.madre_tipo, tipo_preñez: json.preniez.tipo }, ...PARTOS];
    actualizarMadresPreniadas();
    recomputarKpis();
    sincronizarEventos();
    renderTabla();
    renderPartos();
    renderInseminaciones();
    bootstrap.Modal.getOrCreateInstance($('modalParto')).hide();
    if (json.parto.vivo) {
      abrirModalCria(json.preniez, json.parto);
    } else {
      alert('Parto registrado correctamente.');
    }
  }

  function abrirModalCria(p, parto) {
    $('form-cria').reset();
    $('c-parto-id').value = parto.id;
    $('c-tipo').value = p.madre_tipo;
    $('c-madre').value = p.madre_id;
    $('c-padre').value = p.padre_id || '';
    $('c-fecha-nacimiento').value = parto.fecha;
    $('cria-info').innerHTML = `Cría de <strong>#${escapeHtml(p.madre_caravana)} ${escapeHtml(p.madre_nombre)}</strong> · Nacida el <strong>${fmtFecha(parto.fecha)}</strong> · Especie: ${p.madre_tipo}${p.padre ? ` · Padre: <strong>${escapeHtml(p.padre)}</strong>` : ''}`;
    bootstrap.Modal.getOrCreateInstance($('modalCria')).show();
  }

  async function guardarCria() {
    const formData = new FormData();
    formData.append('tipo_animal', $('c-tipo').value);
    formData.append('sexo', $('c-sexo').value);
    formData.append('id_senasa', $('c-senasa').value || '');
    formData.append('nombre', $('c-nombre').value || '');
    formData.append('raza', $('c-raza').value || '');
    formData.append('color', $('c-color').value || '');
    formData.append('peso_al_nacer', $('c-peso').value || '');
    formData.append('fecha_nacimiento', $('c-fecha-nacimiento').value || '');
    formData.append('madre_id', $('c-madre').value || '');
    formData.append('padre_id', $('c-padre').value || '');
    formData.append('parto_id', $('c-parto-id').value || '');
    formData.append('movimiento_tipo', 'Nacimiento');
    formData.append('movimiento_fecha', $('c-fecha-nacimiento').value || '');
    const response = await fetch('/api/animales/', {
      method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: formData,
    });
    const json = await response.json();
    if (!response.ok) {
      alert(json.error || 'No se pudo registrar la cría.');
      return;
    }
    const partoId = Number($('c-parto-id').value);
    const idx = PRENIECES.findIndex((x) => x.parto_id === partoId);
    const cria = { id: json.id, nombre: json.animal.nombre, caravana: json.animal.caravana, sexo: json.animal.sexo };
    if (idx >= 0) {
      PRENIECES[idx] = { ...PRENIECES[idx], crias: [...(PRENIECES[idx].crias || []), cria] };
      PRENIECES = [...PRENIECES];
    }
    PARTOS = PARTOS.map((pt) => (pt.id === partoId ? { ...pt, crias: [...(pt.crias || []), cria] } : pt));
    if (cria.sexo === 'Hembra') {
      MADRES = [...MADRES, { id: cria.id, caravana: cria.caravana, nombre: cria.nombre, tipo: $('c-tipo').value, parcela: 'Sin asignar', preniada: false }];
    }
    actualizarMadresPreniadas();
    recomputarKpis();
    sincronizarEventos();
    renderTabla();
    renderPartos();
    renderInseminaciones();
    bootstrap.Modal.getOrCreateInstance($('modalCria')).hide();
    alert(`Cría ${cria.nombre} (#${cria.caravana}) registrada correctamente.`);
  }

  async function eliminarPreniez(id) {
    if (!window.confirm('¿Eliminar definitivamente esta preñez?')) return;
    const response = await fetch(`/api/prenieces/${id}/eliminar/`, {
      method: 'POST', headers: { 'X-CSRFToken': csrf() },
    });
    if (!response.ok) {
      alert('No se pudo eliminar la preñez.');
      return;
    }
    PRENIECES = PRENIECES.filter((x) => x.id !== id);
    PARTOS = PARTOS.filter((pt) => pt.preniez_id !== id);
    actualizarMadresPreniadas();
    recomputarKpis();
    sincronizarEventos();
    renderTabla();
    renderPartos();
    renderInseminaciones();
  }

  document.addEventListener('DOMContentLoaded', () => {
    renderKpis();
    renderTabla();
    renderPartos();
    renderInseminaciones();

    $('f-especie').innerHTML = '<option value="">Todas</option>' + ESPECIES.map((e) => `<option>${e}</option>`).join('');
    $('f-tipo').innerHTML = '<option value="">Todos</option>' + TIPOS.map((t) => `<option>${t}</option>`).join('');
    $('f-estado').innerHTML = '<option value="">Todos</option>' + ESTADOS.map((e) => `<option>${e}</option>`).join('');
    $('f-parto-especie').innerHTML = '<option value="">Todas</option>' + ESPECIES.map((e) => `<option>${e}</option>`).join('');

    ['f-buscar', 'f-especie', 'f-tipo', 'f-estado'].forEach((id) => {
      $(id).addEventListener('input', () => {
        paginaActual = 1;
        renderTabla();
      });
    });
    $('f-limpiar').addEventListener('click', () => {
      $('f-buscar').value = '';
      $('f-especie').value = '';
      $('f-tipo').value = '';
      $('f-estado').value = '';
      paginaActual = 1;
      renderTabla();
    });

    ['f-parto-buscar', 'f-parto-estado', 'f-parto-especie'].forEach((id) => {
      $(id).addEventListener('input', () => {
        paginaPartosActual = 1;
        renderPartos();
      });
    });
    $('f-parto-limpiar').addEventListener('click', () => {
      $('f-parto-buscar').value = '';
      $('f-parto-estado').value = '';
      $('f-parto-especie').value = '';
      paginaPartosActual = 1;
      renderPartos();
    });

    ['f-insem-buscar', 'f-insem-estado', 'f-insem-padre'].forEach((id) => {
      $(id).addEventListener('input', () => {
        paginaInsemActual = 1;
        renderInseminaciones();
      });
    });
    $('f-insem-limpiar').addEventListener('click', () => {
      $('f-insem-buscar').value = '';
      $('f-insem-estado').value = '';
      $('f-insem-padre').value = '';
      paginaInsemActual = 1;
      renderInseminaciones();
    });

    $('p-padre').innerHTML = '<option value="">No registrado</option>' +
      PADRES.map((padre) => `<option value="${padre.id}">${escapeHtml(padre.nombre)}</option>`).join('');
    $('p-tipo').innerHTML = TIPOS.map((t) => `<option>${t}</option>`).join('');
    $('p-estado').innerHTML = ESTADOS.map((e) => `<option>${e}</option>`).join('');

    $('p-madre-search').addEventListener('input', () => renderMadresSelect($('p-madre-search').value));
    $('p-madre').addEventListener('change', actualizarEstimacion);
    $('p-fecha').addEventListener('change', actualizarEstimacion);

    const opcionesPadres = '<option value="">Seleccionar...</option>' +
      PADRES.map((padre) => `<option value="${padre.id}">${escapeHtml(padre.nombre)}</option>`).join('');
    $('insem-padre').innerHTML = opcionesPadres;
    $('f-insem-padre').innerHTML = '<option value="">Todos</option>' +
      PADRES.map((padre) => `<option value="${padre.id}">${escapeHtml(padre.nombre)}</option>`).join('');
    $('insem-veterinario').innerHTML = '<option value="">No registrado</option>' +
      VETERINARIOS.map((v) => `<option value="${v.id}">${escapeHtml(v.nombre_completo || `${v.apellido || ''} ${v.nombre}`.trim())}</option>`).join('');

    $('insem-animales-search').addEventListener('input', () => renderInsemAnimales($('insem-animales-search').value));
    $('insem-animales').addEventListener('change', () => {
      $('insem-animales-info').textContent = `${seleccionadasInsem().length} hembra(s) seleccionada(s)`;
    });

    document.querySelector('[data-bs-target="#modalInseminacion"]').addEventListener('click', resetFormInseminacion);
    $('modalInseminacion').addEventListener('hidden.bs.modal', resetFormInseminacion);
    $('btn-guardar-inseminacion').addEventListener('click', guardarInseminacion);
    $('btn-guardar-preniadas').addEventListener('click', guardarPreniadas);

    document.querySelector('[data-bs-target="#modalPreniez"]').addEventListener('click', resetFormPreniez);
    $('modalPreniez').addEventListener('hidden.bs.modal', resetFormPreniez);
    $('btn-guardar-preniez').addEventListener('click', guardarPreniez);
    $('btn-guardar-parto').addEventListener('click', guardarParto);
    $('btn-guardar-cria').addEventListener('click', guardarCria);
  });
})();
