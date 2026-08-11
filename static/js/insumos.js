function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
  return '';
}

function buildHeaders(includeJson = false) {
  const headers = {};
  const csrfToken = getCookie('csrftoken');
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;
  headers['X-Requested-With'] = 'XMLHttpRequest';
  if (includeJson) headers['Content-Type'] = 'application/json';
  return headers;
}

document.addEventListener('DOMContentLoaded', () => {
  const tbody = document.getElementById('tabla-insumos-body');
  const buscarInput = document.getElementById('f-buscar-insumos');
  const tipoSelect = document.getElementById('f-tipo-insumo');
  const limpiarBtn = document.getElementById('btn-limpiar-filtros');
  const modalEl = document.getElementById('modalInsumo');
  const form = document.getElementById('form-insumo');
  const guardarBtn = document.getElementById('btn-guardar-insumo');
  const modalTitle = document.getElementById('modalInsumoTitle');
  const unidadSelect = document.getElementById('insumo-unidad');
  const unidadOtroInput = document.getElementById('insumo-unidad-otro');
  const UNIDADES_PREDEFINIDAS = ['Kg', 'Gr', 'Dosis', 'Unidad', 'Litros'];

  const toggleUnidadOtro = () => {
    const esOtro = unidadSelect.value === 'Otro';
    unidadOtroInput.classList.toggle('d-none', !esOtro);
    if (!esOtro) unidadOtroInput.value = '';
  };

  const state = {
    items: [],
    visibleDetailId: null,
    lotesByInsumo: {},
    editingId: null,
  };

  const escapeHtml = (value) =>
    String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[char]));

  const renderLoteRows = (insumoId, lotes = []) => {
    if (!lotes.length) {
      return '<tr><td colspan="4" class="text-center text-secondary">No hay lotes registrados.</td></tr>';
    }

    return lotes
      .map(
        (lote) => `
      <tr>
        <td>${escapeHtml(lote.nombre || '—')}</td>
        <td>${escapeHtml(lote.fecha_vencimiento || '—')}</td>
        <td>${escapeHtml(lote.stock_actual)}</td>
        <td class="text-end">
          <button type="button" class="btn btn-sm btn-outline-secondary me-1 btn-edit-lote" data-id="${lote.id}" data-insumo-id="${insumoId}"><i class="bi bi-pencil"></i></button>
          <button type="button" class="btn btn-sm btn-outline-danger btn-delete-lote" data-id="${lote.id}" data-insumo-id="${insumoId}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>
    `,
      )
      .join('');
  };

  const renderDetailRow = (item) => {
    const lotes = state.lotesByInsumo[item.id] || [];
    const detailBgClass = 'bg-body-secondary bg-opacity-10';
    return `
      <tr class="insumo-detail-row d-none border-bottom" data-id="${item.id}">
        <td colspan="5" class="p-0 ${detailBgClass}">
          <div class="py-2">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <div><strong>Lotes de ${escapeHtml(item.nombre)}</strong></div>
              <button type="button" class="btn btn-sm btn-outline-success btn-add-lote" data-insumo-id="${item.id}">Agregar lote</button>
            </div>
            <div class="mb-3 lote-form d-none" data-insumo-id="${item.id}">
              <div class="row g-3">
                <input type="hidden" id="lote-id-${item.id}" />
                <div class="col-md-4">
                  <label class="form-label">Nombre</label>
                  <input type="text" id="lote-nombre-${item.id}" class="form-control" />
                </div>
                <div class="col-md-4">
                  <label class="form-label">Fecha de vencimiento</label>
                  <input type="date" id="lote-vencimiento-${item.id}" class="form-control" />
                </div>
                <div class="col-md-4">
                  <label class="form-label">Stock actual</label>
                  <input type="number" step="0.01" min="0" id="lote-stock-${item.id}" class="form-control" value="0" />
                </div>
              </div>
              <div class="mt-3 text-end">
                <button type="button" class="btn btn-outline-secondary btn-sm btn-cancel-lote" data-insumo-id="${item.id}">Cancelar</button>
                <button type="button" class="btn btn-success btn-sm btn-save-lote" data-insumo-id="${item.id}">Guardar lote</button>
              </div>
            </div>
            <div class="table-responsive">
              <table class="table table-sm mb-0">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Fecha de vencimiento</th>
                    <th>Stock actual</th>
                    <th class="text-end">Acciones</th>
                  </tr>
                </thead>
                <tbody class="insumo-lotes-body" data-insumo-id="${item.id}">
                  ${renderLoteRows(item.id, lotes)}
                </tbody>
              </table>
            </div>
          </div>
        </td>
      </tr>
    `;
  };

  const renderRows = () => {
    const query = buscarInput.value.trim().toLowerCase();
    const tipo = tipoSelect.value;
    const filtered = state.items.filter((item) => {
      const matchesQuery = !query || `${item.nombre} ${item.tipo}`.toLowerCase().includes(query);
      const matchesTipo = !tipo || item.tipo === tipo;
      return matchesQuery && matchesTipo;
    });

    if (!tbody) return;

    tbody.innerHTML = filtered.length
      ? filtered
          .map(
            (item) => `
      <tr class="insumo-row" data-id="${item.id}">
        <td>${escapeHtml(item.nombre)}</td>
        <td>${escapeHtml(item.tipo)}</td>
        <td>${escapeHtml(item.unidad_de_medida)}</td>
        <td>${escapeHtml(item.cantidad_total)}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary me-1 btn-toggle-lotes" data-id="${item.id}" title="Ver lotes"><i class="bi bi-eye"></i></button>
          <button class="btn btn-sm btn-outline-secondary me-1 btn-edit-insumo" data-id="${item.id}" title="Editar insumo"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger btn-delete-insumo" data-id="${item.id}" title="Eliminar insumo"><i class="bi bi-trash"></i></button>
        </td>
      </tr>
      ${renderDetailRow(item)}
    `,
          )
          .join('')
      : '<tr><td colspan="5" class="text-center text-secondary">No hay insumos para mostrar.</td></tr>';
  };

  const loadItems = async () => {
    const params = new URLSearchParams();
    if (buscarInput.value.trim()) params.set('q', buscarInput.value.trim());
    if (tipoSelect.value) params.set('tipo', tipoSelect.value);
    const response = await fetch(`/api/insumos/?${params.toString()}`, { headers: buildHeaders() });
    const payload = await response.json();
    state.items = payload.insumos || [];
    renderRows();
    actualizarKpis();
  };

  const actualizarKpis = () => {
    const total = state.items.length;
    const vacunas = state.items.filter((item) => item.tipo === 'Vacuna').length;
    const medicamentos = state.items.filter((item) => item.tipo === 'Medicamento').length;
    const alimentos = state.items.filter((item) => item.tipo === 'Alimento').length;
    document.getElementById('kpi-total-insumos').textContent = total;
    document.getElementById('kpi-vacunas').textContent = vacunas;
    document.getElementById('kpi-medicamentos').textContent = medicamentos;
    document.getElementById('kpi-alimentos').textContent = alimentos;
  };

  const toggleDetailRow = async (insumoId, row) => {
    const detailRow = row.nextElementSibling;
    if (!detailRow || !detailRow.classList.contains('insumo-detail-row')) return;

    if (!detailRow.classList.contains('d-none')) {
      detailRow.classList.add('d-none');
      state.visibleDetailId = null;
      return;
    }

    const lotes = await fetchLotes(insumoId);
    state.lotesByInsumo[insumoId] = lotes;

    const body = detailRow.querySelector('.insumo-lotes-body');
    if (body) body.innerHTML = renderLoteRows(insumoId, lotes);
    detailRow.classList.remove('d-none');
    state.visibleDetailId = insumoId;
  };

  const fetchLotes = async (insumoId) => {
    const response = await fetch(`/api/insumos/${insumoId}/`, { headers: buildHeaders() });
    if (!response.ok) return [];
    const payload = await response.json();
    return payload.insumo.lotes || [];
  };

  const openModal = async (item = null) => {
    form.reset();
    document.getElementById('insumo-id').value = '';
    modalTitle.textContent = 'Registrar insumo';
    state.editingId = null;
    unidadSelect.value = 'Kg';
    toggleUnidadOtro();

    if (item) {
      const response = await fetch(`/api/insumos/${item.id}/`, { headers: buildHeaders() });
      if (!response.ok) {
        alert('No se pudo cargar el detalle del insumo.');
        return;
      }
      const payload = await response.json();
      const detail = payload.insumo;
      document.getElementById('insumo-id').value = detail.id;
      document.getElementById('insumo-nombre').value = detail.nombre || '';
      document.getElementById('insumo-tipo').value = detail.tipo || 'Otros';
      const unidad = (detail.unidad_de_medida || '').trim();
      const match = UNIDADES_PREDEFINIDAS.find((op) => op.toLowerCase() === unidad.toLowerCase());
      if (match) {
        unidadSelect.value = match;
      } else {
        unidadSelect.value = 'Otro';
        unidadOtroInput.value = unidad;
      }
      toggleUnidadOtro();
      modalTitle.textContent = 'Editar insumo';
      state.editingId = detail.id;
    }

    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  };

  const saveInsumo = async () => {
    const payload = new FormData();
    payload.set('nombre', document.getElementById('insumo-nombre').value.trim());
    payload.set('tipo', document.getElementById('insumo-tipo').value);
    let unidad = unidadSelect.value;
    if (unidad === 'Otro') unidad = unidadOtroInput.value.trim();
    payload.set('unidad_de_medida', unidad || 'kg');

    const url = state.editingId ? `/api/insumos/${state.editingId}/` : '/api/insumos/';
    const response = await fetch(url, { method: 'POST', body: payload, headers: buildHeaders() });
    const result = await response.json();
    if (!response.ok) {
      alert(result.error || 'No se pudo guardar el insumo');
      return;
    }

    bootstrap.Modal.getInstance(modalEl)?.hide();
    await loadItems();
  };

  const showInlineLoteForm = (insumoId, lote = null) => {
    const formSection = document.querySelector(`.lote-form[data-insumo-id="${insumoId}"]`);
    if (!formSection) return;
    const idField = formSection.querySelector(`#lote-id-${insumoId}`);
    const nombreField = formSection.querySelector(`#lote-nombre-${insumoId}`);
    const vencimientoField = formSection.querySelector(`#lote-vencimiento-${insumoId}`);
    const stockField = formSection.querySelector(`#lote-stock-${insumoId}`);

    if (lote) {
      idField.value = lote.id;
      nombreField.value = lote.nombre || '';
      vencimientoField.value = lote.fecha_vencimiento || '';
      stockField.value = lote.stock_actual || '0';
    } else {
      idField.value = '';
      nombreField.value = '';
      vencimientoField.value = '';
      stockField.value = '0';
    }

    formSection.classList.remove('d-none');
  };

  const hideInlineLoteForm = (insumoId) => {
    const formSection = document.querySelector(`.lote-form[data-insumo-id="${insumoId}"]`);
    if (!formSection) return;
    formSection.classList.add('d-none');
  };

  const saveInlineLote = async (insumoId) => {
    const formSection = document.querySelector(`.lote-form[data-insumo-id="${insumoId}"]`);
    if (!formSection) return;
    const idField = formSection.querySelector(`#lote-id-${insumoId}`);
    const nombreField = formSection.querySelector(`#lote-nombre-${insumoId}`);
    const vencimientoField = formSection.querySelector(`#lote-vencimiento-${insumoId}`);
    const stockField = formSection.querySelector(`#lote-stock-${insumoId}`);

    const payload = new FormData();
    payload.set('nombre', nombreField.value.trim());
    payload.set('fecha_vencimiento', vencimientoField.value || '');
    payload.set('stock_actual', stockField.value || '0');

    const loteId = idField.value;
    const url = loteId ? `/api/lotes/${loteId}/` : `/api/insumos/${insumoId}/lotes/`;
    const response = await fetch(url, { method: 'POST', body: payload, headers: buildHeaders() });
    const result = await response.json();
    if (!response.ok) {
      alert(result.error || 'No se pudo guardar el lote');
      return;
    }

    hideInlineLoteForm(insumoId);
    const row = document.querySelector(`tr.insumo-row[data-id="${insumoId}"]`);
    if (row) await toggleDetailRow(insumoId, row);
    if (row) await toggleDetailRow(insumoId, row);
  };

  const deleteInlineLote = async (loteId, insumoId) => {
    if (!confirm('¿Dar de baja este lote? No se eliminarán las compras ni los consumos asociados.')) return;
    const response = await fetch(`/api/lotes/${loteId}/`, { method: 'DELETE', headers: buildHeaders() });
    if (!response.ok) {
      alert('No se pudo eliminar el lote');
      return;
    }
    const row = document.querySelector(`tr.insumo-row[data-id="${insumoId}"]`);
    if (row) await toggleDetailRow(insumoId, row);
    if (row) await toggleDetailRow(insumoId, row);
  };

  const editInlineLote = async (loteId, insumoId) => {
    const lotes = await fetchLotes(insumoId);
    const lote = lotes.find((item) => item.id === loteId);
    if (!lote) return;
    state.lotesByInsumo[insumoId] = lotes;
    const row = document.querySelector(`tr.insumo-row[data-id="${insumoId}"]`);
    if (!row) return;
    const detailRow = row.nextElementSibling;
    if (!detailRow || !detailRow.classList.contains('insumo-detail-row')) return;
    if (detailRow.classList.contains('d-none')) {
      await toggleDetailRow(insumoId, row);
    }
    showInlineLoteForm(insumoId, lote);
  };

  guardarBtn.addEventListener('click', saveInsumo);
  unidadSelect.addEventListener('change', toggleUnidadOtro);
  limpiarBtn.addEventListener('click', () => {
    buscarInput.value = '';
    tipoSelect.value = '';
    loadItems();
  });
  buscarInput.addEventListener('input', loadItems);
  tipoSelect.addEventListener('change', loadItems);

  tbody.addEventListener('click', async (event) => {
    const toggleLotesButton = event.target.closest('.btn-toggle-lotes');
    const editInsumoButton = event.target.closest('.btn-edit-insumo');
    const deleteInsumoButton = event.target.closest('.btn-delete-insumo');
    const addLoteButton = event.target.closest('.btn-add-lote');
    const saveLoteButton = event.target.closest('.btn-save-lote');
    const cancelLoteButton = event.target.closest('.btn-cancel-lote');
    const editLoteButton = event.target.closest('.btn-edit-lote');
    const deleteLoteButton = event.target.closest('.btn-delete-lote');
    const row = event.target.closest('tr.insumo-row');

    if (toggleLotesButton && row) {
      const insumoId = Number(toggleLotesButton.dataset.id);
      await toggleDetailRow(insumoId, row);
      return;
    }

    if (editInsumoButton) {
      const id = Number(editInsumoButton.dataset.id);
      const item = state.items.find((entry) => entry.id === id);
      if (item) openModal(item);
      return;
    }

    if (deleteInsumoButton) {
      const id = Number(deleteInsumoButton.dataset.id);
      if (!confirm('¿Dar de baja este insumo? No se eliminarán las compras ni los eventos sanitarios asociados.')) return;
      const response = await fetch(`/api/insumos/${id}/`, { method: 'DELETE', headers: buildHeaders() });
      if (response.ok) {
        await loadItems();
      }
      return;
    }

    if (addLoteButton) {
      const insumoId = Number(addLoteButton.dataset.insumoId);
      showInlineLoteForm(insumoId);
      return;
    }

    if (saveLoteButton) {
      const insumoId = Number(saveLoteButton.dataset.insumoId);
      await saveInlineLote(insumoId);
      return;
    }

    if (cancelLoteButton) {
      const insumoId = Number(cancelLoteButton.dataset.insumoId);
      hideInlineLoteForm(insumoId);
      return;
    }

    if (editLoteButton) {
      const loteId = Number(editLoteButton.dataset.id);
      const insumoId = Number(editLoteButton.dataset.insumoId);
      await editInlineLote(loteId, insumoId);
      return;
    }

    if (deleteLoteButton) {
      const loteId = Number(deleteLoteButton.dataset.id);
      const insumoId = Number(deleteLoteButton.dataset.insumoId);
      await deleteInlineLote(loteId, insumoId);
      return;
    }
  });

  document.querySelector('[data-bs-target="#modalInsumo"]').addEventListener('click', () => openModal());
  loadItems();
});
