(() => {
  'use strict';

  const data = window.GANASTOCK_DATA || {};

  let PRENIECES = data.prenieces || [];
  let MADRES = data.madres || [];
  let PADRES = data.padres || [];
  let VETERINARIOS = data.veterinarios || [];
  let KPIS = data.kpis || {};

  const TIPOS = data.tipos || ['Natural', 'Inseminación'];
  const ESTADOS = data.estados || ['Preñada', 'A confirmar', 'Vacía'];
  const MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const ESTADO_BADGE = {
    'Preñada': 'text-bg-success',
    'A confirmar': 'text-bg-warning',
    'Vacía': 'text-bg-secondary',
  };
  const FILAS_POR_PAGINA = 5;
  let paginaActual = 1;

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
    const tipo = $('f-tipo').value;
    const estado = $('f-estado').value;
    return PRENIECES.filter((p) => {
      const hayBusqueda = `${p.madre_caravana} ${p.madre_nombre} ${p.padre} ${p.detalle}`.toLowerCase();
      return (!buscar || hayBusqueda.includes(buscar)) && (!tipo || p.tipo === tipo) && (!estado || p.estado_actual === estado);
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
    $('p-veterinario').value = p.veterinario_id || '';
    $('p-fecha').value = p.fecha;
    $('p-tipo').value = p.tipo;
    $('p-estado').value = p.estado_actual;
    $('p-costo').value = p.costo_inseminacion || '';
    $('p-detalle').value = p.detalle || '';
    actualizarEstimacion();
    bootstrap.Modal.getOrCreateInstance($('modalPreniez')).show();
  }

  async function guardarPreniez() {
    const id = $('preniez-id').value;
    const formData = new FormData();
    formData.append('madre_id', $('p-madre').value);
    formData.append('padre_id', $('p-padre').value || '');
    formData.append('veterinario_id', $('p-veterinario').value || '');
    formData.append('fecha', $('p-fecha').value);
    formData.append('tipo', $('p-tipo').value);
    formData.append('estado_actual', $('p-estado').value);
    formData.append('costo_inseminacion', $('p-costo').value || '');
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
    actualizarMadresPreniadas();
    recomputarKpis();
    renderTabla();
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
    $('det-veterinario').textContent = p.veterinario;
    $('det-costo').textContent = dinero(p.costo_inseminacion);
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
    actualizarMadresPreniadas();
    recomputarKpis();
    renderTabla();
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
    $('c-fecha-nacimiento').value = parto.fecha;
    $('cria-info').innerHTML = `Cría de <strong>#${escapeHtml(p.madre_caravana)} ${escapeHtml(p.madre_nombre)}</strong> · Nacida el <strong>${fmtFecha(parto.fecha)}</strong> · Especie: ${p.madre_tipo}`;
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
    if (cria.sexo === 'Hembra') {
      MADRES = [...MADRES, { id: cria.id, caravana: cria.caravana, nombre: cria.nombre, tipo: $('c-tipo').value, parcela: 'Sin asignar', preniada: false }];
    }
    recomputarKpis();
    renderTabla();
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
    actualizarMadresPreniadas();
    recomputarKpis();
    renderTabla();
  }

  document.addEventListener('DOMContentLoaded', () => {
    renderKpis();
    renderTabla();

    $('f-tipo').innerHTML = '<option value="">Todos</option>' + TIPOS.map((t) => `<option>${t}</option>`).join('');
    $('f-estado').innerHTML = '<option value="">Todos</option>' + ESTADOS.map((e) => `<option>${e}</option>`).join('');

    ['f-buscar', 'f-tipo', 'f-estado'].forEach((id) => {
      $(id).addEventListener('input', () => {
        paginaActual = 1;
        renderTabla();
      });
    });
    $('f-limpiar').addEventListener('click', () => {
      $('f-buscar').value = '';
      $('f-tipo').value = '';
      $('f-estado').value = '';
      paginaActual = 1;
      renderTabla();
    });

    $('p-padre').innerHTML = '<option value="">No registrado</option>' +
      PADRES.map((padre) => `<option value="${padre.id}">${escapeHtml(padre.nombre)}</option>`).join('');
    $('p-veterinario').innerHTML = '<option value="">No registrado</option>' +
      VETERINARIOS.map((v) => `<option value="${v.id}">${escapeHtml(v.nombre_completo || `${v.apellido || ''} ${v.nombre}`.trim())}</option>`).join('');
    $('p-tipo').innerHTML = TIPOS.map((t) => `<option>${t}</option>`).join('');
    $('p-estado').innerHTML = ESTADOS.map((e) => `<option>${e}</option>`).join('');

    $('p-madre-search').addEventListener('input', () => renderMadresSelect($('p-madre-search').value));
    $('p-madre').addEventListener('change', actualizarEstimacion);
    $('p-fecha').addEventListener('change', actualizarEstimacion);

    document.querySelector('[data-bs-target="#modalPreniez"]').addEventListener('click', resetFormPreniez);
    $('modalPreniez').addEventListener('hidden.bs.modal', resetFormPreniez);
    $('btn-guardar-preniez').addEventListener('click', guardarPreniez);
    $('btn-guardar-parto').addEventListener('click', guardarParto);
    $('btn-guardar-cria').addEventListener('click', guardarCria);
  });
})();
