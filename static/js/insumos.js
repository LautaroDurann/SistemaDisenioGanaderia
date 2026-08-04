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

  const state = {
    items: [],
    editingId: null,
  };

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  const renderRows = () => {
    const query = buscarInput.value.trim().toLowerCase();
    const tipo = tipoSelect.value;
    const filtered = state.items.filter((item) => {
      const matchesQuery = !query || `${item.nombre} ${item.tipo}`.toLowerCase().includes(query);
      const matchesTipo = !tipo || item.tipo === tipo;
      return matchesQuery && matchesTipo;
    });

    if (!tbody) return;

    tbody.innerHTML = filtered.length ? filtered.map((item) => `
      <tr>
        <td>${escapeHtml(item.nombre)}</td>
        <td>${escapeHtml(item.tipo)}</td>
        <td>${escapeHtml(item.unidad_de_medida)}</td>
        <td>${escapeHtml(item.stock_actual)}</td>
        <td>${escapeHtml(item.fecha_vencimiento || '—')}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary me-1 btn-editar" data-id="${item.id}"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger btn-eliminar" data-id="${item.id}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>
    `).join('') : '<tr><td colspan="6" class="text-center text-secondary">No hay insumos para mostrar.</td></tr>';
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
    const stockTotal = state.items.reduce((acc, item) => acc + Number(item.stock_actual || 0), 0);
    document.getElementById('kpi-total-insumos').textContent = total;
    document.getElementById('kpi-vacunas').textContent = vacunas;
    document.getElementById('kpi-medicamentos').textContent = medicamentos;
    document.getElementById('kpi-stock-total').textContent = stockTotal.toFixed(2);
  };

  const resetForm = () => {
    form.reset();
    document.getElementById('insumo-id').value = '';
    document.getElementById('insumo-unidad').value = 'kg';
    document.getElementById('insumo-stock').value = '0';
    document.getElementById('insumo-tipo').value = 'Vacuna';
    modalTitle.textContent = 'Registrar insumo';
    state.editingId = null;
  };

  const openModal = (item = null) => {
    resetForm();
    if (item) {
      document.getElementById('insumo-id').value = item.id;
      document.getElementById('insumo-nombre').value = item.nombre;
      document.getElementById('insumo-tipo').value = item.tipo;
      document.getElementById('insumo-unidad').value = item.unidad_de_medida;
      document.getElementById('insumo-stock').value = item.stock_actual;
      document.getElementById('insumo-vencimiento').value = item.fecha_vencimiento || '';
      modalTitle.textContent = 'Editar insumo';
      state.editingId = item.id;
    }
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  };

  const saveInsumo = async () => {
    const payload = new FormData();
    payload.set('nombre', document.getElementById('insumo-nombre').value.trim());
    payload.set('tipo', document.getElementById('insumo-tipo').value);
    payload.set('unidad_de_medida', document.getElementById('insumo-unidad').value.trim() || 'kg');
    payload.set('stock_actual', document.getElementById('insumo-stock').value);
    payload.set('fecha_vencimiento', document.getElementById('insumo-vencimiento').value || '');

    const url = state.editingId ? `/api/insumos/${state.editingId}/` : '/api/insumos/';
    const method = state.editingId ? 'POST' : 'POST';

    const response = await fetch(url, {
      method,
      body: payload,
      headers: buildHeaders(),
    });
    const result = await response.json();
    if (!response.ok) {
      alert(result.error || 'No se pudo guardar el insumo');
      return;
    }

    bootstrap.Modal.getInstance(modalEl)?.hide();
    resetForm();
    await loadItems();
  };

  guardarBtn.addEventListener('click', saveInsumo);
  limpiarBtn.addEventListener('click', () => {
    buscarInput.value = '';
    tipoSelect.value = '';
    loadItems();
  });
  buscarInput.addEventListener('input', loadItems);
  tipoSelect.addEventListener('change', loadItems);

  tbody.addEventListener('click', async (event) => {
    const editButton = event.target.closest('.btn-editar');
    const deleteButton = event.target.closest('.btn-eliminar');
    if (editButton) {
      const id = Number(editButton.dataset.id);
      const item = state.items.find((entry) => entry.id === id);
      if (item) openModal(item);
      return;
    }
    if (deleteButton) {
      const id = Number(deleteButton.dataset.id);
      if (!confirm('¿Desea eliminar este insumo?')) return;
      const response = await fetch(`/api/insumos/${id}/`, { method: 'DELETE', headers: buildHeaders() });
      if (response.ok) {
        await loadItems();
      }
    }
  });

  document.querySelector('[data-bs-target="#modalInsumo"]').addEventListener('click', () => openModal());
  loadItems();
});
