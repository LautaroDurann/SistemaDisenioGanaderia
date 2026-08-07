function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

const dinero = (v) => `$ ${Number(v || 0).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const mesClave = (fechaISO) => fechaISO.slice(0, 7);
const mesActualClave = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

let chartInstance = null;
let chartLabels = Array.isArray(window.CHART_LABELS) ? [...window.CHART_LABELS] : [];
let chartIngresos = Array.isArray(window.CHART_INGRESOS) ? [...window.CHART_INGRESOS] : [];
let chartEgresos = Array.isArray(window.CHART_EGRESOS) ? [...window.CHART_EGRESOS] : [];
let kpiTotal = typeof KPI_TOTAL !== 'undefined' ? Number(KPI_TOTAL || 0) : 0;
let kpiIngresos = typeof KPI_INGRESOS !== 'undefined' ? Number(KPI_INGRESOS || 0) : 0;
let kpiEgresos = typeof KPI_EGRESOS !== 'undefined' ? Number(KPI_EGRESOS || 0) : 0;
let kpiBalance = typeof KPI_BALANCE !== 'undefined' ? Number(KPI_BALANCE || 0) : 0;

function filaMovimientoHTML(m) {
  const esIngreso = m.tipo === 'Ingreso';
  return `<tr data-id="${m.id}" data-tipo="${m.tipo}" data-monto="${m.monto_total}" data-fecha="${m.fecha}" data-nombre="${m.nombre}">
    <td>${m.fecha}</td>
    <td><span class="badge ${esIngreso ? 'text-bg-success' : 'text-bg-danger'}">${m.tipo}</span></td>
    <td>${m.nombre}</td>
    <td>${m.detalle || '-'}</td>
    <td class="text-end">${dinero(m.monto_total)}</td>
    <td class="text-end">
      <div class="d-flex gap-1 justify-content-end">
        <button class="btn btn-sm btn-outline-secondary btn-ver" data-id="${m.id}" title="Ver detalle"><i class="bi bi-eye"></i></button>
        <button class="btn btn-sm btn-outline-primary btn-editar" data-id="${m.id}" title="Editar"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger btn-eliminar" data-id="${m.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
      </div>
    </td>
  </tr>`;
}

function verMovimiento(row) {
  const id = row.dataset.id;
  const tipo = row.dataset.tipo;
  const monto = row.children[4]?.textContent.trim() || '';
  document.getElementById('det-fecha').textContent = row.children[0].textContent.trim();
  document.getElementById('det-tipo').textContent = tipo;
  document.getElementById('det-nombre').textContent = row.children[2].textContent.trim();
  document.getElementById('det-detalle').textContent = row.children[3].textContent.trim();
  document.getElementById('det-monto').textContent = monto;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('modalVerMovimientoFinanciero')).show();
}

function abrirEdicionMovimiento(row) {
  document.getElementById('mov-id').value = row.dataset.id;
  document.getElementById('mov-fecha').value = row.dataset.fecha;
  document.getElementById('mov-tipo').value = row.dataset.tipo;
  document.getElementById('mov-monto').value = row.dataset.monto;
  document.getElementById('mov-nombre').value = row.children[2].textContent.trim();
  document.getElementById('mov-detalle').value = row.children[3].textContent.trim() === '-' ? '' : row.children[3].textContent.trim();
  document.getElementById('titulo-mov-modal').textContent = 'Editar movimiento financiero';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('modalRegistrarMovimientoFinanciero')).show();
}

function enviarMovimiento(payload, url) {
  return fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCookie('csrftoken') },
    body: payload,
  });
}

function aplicarFiltros() {
  const tbody = document.getElementById('tabla-finanzas-body');
  if (!tbody) return;
  const desde = document.getElementById('filtro-desde')?.value || '';
  const hasta = document.getElementById('filtro-hasta')?.value || '';
  const concepto = (document.getElementById('filtro-concepto')?.value || '').trim().toLowerCase();
  const tipoFiltro = (document.getElementById('f-tipo')?.value || '').trim();

  const hayDatos = tbody.querySelector('tr[data-id]');
  let visibles = 0;
  tbody.querySelectorAll('tr[data-id]').forEach((row) => {
    const fecha = row.dataset.fecha || '';
    const nombre = (row.dataset.nombre || '').toLowerCase();
    const detalle = (row.children[3]?.textContent || '').toLowerCase();
    const tipo = row.dataset.tipo || '';
    let mostrar = true;
    if (desde && fecha < desde) mostrar = false;
    if (hasta && fecha > hasta) mostrar = false;
    if (tipoFiltro && tipoFiltro !== '' && tipo !== tipoFiltro) mostrar = false;
    if (concepto && !(nombre.includes(concepto) || detalle.includes(concepto))) mostrar = false;
    row.style.display = mostrar ? '' : 'none';
    if (mostrar) visibles++;
  });

  const filaVacia = tbody.querySelector('#fila-vacia-movimientos');
  const filaFiltro = tbody.querySelector('.fila-filtro-vacio');
  if (hayDatos && visibles === 0) {
    if (filaVacia) filaVacia.style.display = 'none';
    if (!filaFiltro) {
      tbody.insertAdjacentHTML('beforeend', '<tr class="fila-filtro-vacio"><td colspan="6" class="text-center text-secondary py-4">No se encontraron movimientos para los filtros aplicados.</td></tr>');
    }
  } else {
    if (filaVacia) filaVacia.style.display = '';
    if (filaFiltro) filaFiltro.remove();
  }
}

function limpiarFiltros() {
  ['filtro-desde', 'filtro-hasta', 'filtro-concepto'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  aplicarFiltros();
}

function prependFila(movimiento) {
  const tbody = document.getElementById('tabla-finanzas-body');
  if (!tbody) return;
  const vacia = tbody.querySelector('#fila-vacia-movimientos');
  if (vacia) vacia.remove();
  const filaFiltro = tbody.querySelector('.fila-filtro-vacio');
  if (filaFiltro) filaFiltro.remove();
  tbody.insertAdjacentHTML('afterbegin', filaMovimientoHTML(movimiento));
  aplicarFiltros();
}

function actualizarKPIs(tipo, monto, signo, fechaISO) {
  if (mesClave(fechaISO) !== mesActualClave()) return;
  const montoNum = Number(monto || 0);
  const esIngreso = tipo === 'Ingreso';
  kpiTotal += signo;
  if (esIngreso) kpiIngresos += signo * montoNum;
  else kpiEgresos += signo * montoNum;
  kpiBalance += signo * (esIngreso ? 1 : -1) * montoNum;
  const elTotal = document.getElementById('kpi-total');
  const elIngresos = document.getElementById('kpi-ingresos');
  const elEgresos = document.getElementById('kpi-egresos');
  const elBalance = document.getElementById('kpi-balance');
  if (elTotal) elTotal.textContent = kpiTotal;
  if (elIngresos) elIngresos.textContent = dinero(kpiIngresos);
  if (elEgresos) elEgresos.textContent = dinero(kpiEgresos);
  if (elBalance) elBalance.textContent = dinero(kpiBalance);
}

function actualizarChart(tipo, monto, signo, fechaISO) {
  if (!chartInstance) return;
  const idx = chartLabels.indexOf(mesClave(fechaISO));
  if (idx === -1) return;
  const arr = tipo === 'Ingreso' ? chartIngresos : chartEgresos;
  arr[idx] = Number(arr[idx] || 0) + signo * Number(monto || 0);
  chartInstance.updateSeries([
    { name: 'Ingresos', data: chartIngresos.slice() },
    { name: 'Egresos', data: chartEgresos.slice() },
  ]);
}

document.addEventListener('DOMContentLoaded', function () {
  console.log('finanzas.js loaded');
  chartLabels = Array.isArray(window.CHART_LABELS) ? [...window.CHART_LABELS] : [];
  chartIngresos = Array.isArray(window.CHART_INGRESOS) ? [...window.CHART_INGRESOS] : [];
  chartEgresos = Array.isArray(window.CHART_EGRESOS) ? [...window.CHART_EGRESOS] : [];
  try {
    const chartElement = document.querySelector('#chart-finanzas');
    if (chartElement && chartLabels.length > 0) {
      chartInstance = new ApexCharts(chartElement, {
        chart: { height: 320, type: 'bar', toolbar: { show: false } },
        series: [
          { name: 'Ingresos', data: chartIngresos.slice() },
          { name: 'Egresos', data: chartEgresos.slice() },
        ],
        xaxis: { categories: chartLabels },
        colors: ['#198754', '#dc3545'],
        dataLabels: { enabled: false },
        stroke: { show: true, width: 2, colors: ['transparent'] },
      });
      chartInstance.render().catch(() => {});
    }
  } catch (e) {
    console.error('Error renderizando gráfico de finanzas', e);
  }

  const form = document.getElementById('form-registrar-mov-financiero');
  const modalRegistrar = document.getElementById('modalRegistrarMovimientoFinanciero');
  console.log('finanzas: form', form);
  console.log('finanzas: modalRegistrar', modalRegistrar);
  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      console.log('finanzas: submit movimiento');
      const id = document.getElementById('mov-id').value;
      const fd = new FormData(form);
      const url = id ? `/api/finanzas/movimientos/${id}/` : '/api/finanzas/movimientos/';
      enviarMovimiento(fd, url).then(res => {
        return res.json().then(data => ({ ok: res.ok, data }));
      }).then(({ ok, data }) => {
        if (!ok) {
          const message = data?.error || 'Error al guardar el movimiento.';
          alert(message);
          console.error('finanzas: error response', data);
          return;
        }
        if (data.error) {
          alert(data.error);
          console.error('finanzas: backend error', data.error);
          return;
        }
        const tbody = document.getElementById('tabla-finanzas-body');
        if (id) {
          const row = tbody.querySelector(`tr[data-id="${id}"]`);
          if (row) {
            actualizarKPIs(row.dataset.tipo, row.dataset.monto, -1, row.dataset.fecha);
            actualizarChart(row.dataset.tipo, row.dataset.monto, -1, row.dataset.fecha);
            row.outerHTML = filaMovimientoHTML(data.movimiento);
          }
          actualizarKPIs(data.movimiento.tipo, data.movimiento.monto_total, 1, data.movimiento.fecha);
          actualizarChart(data.movimiento.tipo, data.movimiento.monto_total, 1, data.movimiento.fecha);
          aplicarFiltros();
        } else {
          prependFila(data.movimiento);
          actualizarKPIs(data.movimiento.tipo, data.movimiento.monto_total, 1, data.movimiento.fecha);
          actualizarChart(data.movimiento.tipo, data.movimiento.monto_total, 1, data.movimiento.fecha);
        }
        form.reset();
        bootstrap.Modal.getOrCreateInstance(modalRegistrar).hide();
      }).catch(err => {
        console.error(err);
        alert('Error al guardar el movimiento.');
      });
    });
  }

  if (modalRegistrar) {
    modalRegistrar.addEventListener('hidden.bs.modal', function () {
      document.getElementById('mov-id').value = '';
      document.getElementById('titulo-mov-modal').textContent = 'Registrar movimiento financiero';
      form?.reset();
    });
  }

  const tbody = document.getElementById('tabla-finanzas-body');
  if (tbody) {
    tbody.addEventListener('click', function (e) {
      const btnVer = e.target.closest('.btn-ver');
      if (btnVer) {
        const row = tbody.querySelector(`tr[data-id="${btnVer.dataset.id}"]`);
        if (row) verMovimiento(row);
        return;
      }
      const btnEditar = e.target.closest('.btn-editar');
      if (btnEditar) {
        const row = tbody.querySelector(`tr[data-id="${btnEditar.dataset.id}"]`);
        if (row) abrirEdicionMovimiento(row);
        return;
      }
      const btn = e.target.closest('.btn-eliminar');
      if (!btn) return;
      const id = btn.dataset.id;
      if (!confirm('Confirma eliminar este movimiento financiero?')) return;
      fetch(`/api/finanzas/movimientos/${id}/eliminar/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      }).then(res => res.json()).then(data => {
        if (data.ok) {
          const row = tbody.querySelector(`tr[data-id="${id}"]`);
          if (row) {
            actualizarKPIs(row.dataset.tipo, row.dataset.monto, -1, row.dataset.fecha);
            actualizarChart(row.dataset.tipo, row.dataset.monto, -1, row.dataset.fecha);
            row.remove();
          }
          if (!tbody.querySelector('tr[data-id]')) {
            const filaFiltro = tbody.querySelector('.fila-filtro-vacio');
            if (filaFiltro) filaFiltro.remove();
            tbody.innerHTML = '<tr id="fila-vacia-movimientos"><td colspan="6" class="text-center text-secondary py-4">No hay movimientos financieros registrados.</td></tr>';
          } else {
            aplicarFiltros();
          }
        } else {
          alert(data.error || 'No se pudo eliminar el movimiento.');
        }
      }).catch(err => {
        console.error(err);
        alert('Error al eliminar el movimiento.');
      });
    });
  }

  document.getElementById('filtro-limpiar')?.addEventListener('click', limpiarFiltros);
  document.getElementById('filtro-desde')?.addEventListener('input', aplicarFiltros);
  document.getElementById('filtro-hasta')?.addEventListener('input', aplicarFiltros);
  document.getElementById('filtro-concepto')?.addEventListener('input', aplicarFiltros);
});

