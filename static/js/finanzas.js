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
const temaApex = () =>
  typeof window.huacappTemaApex === 'function'
    ? window.huacappTemaApex()
    : document.documentElement.getAttribute('data-bs-theme') === 'dark'
      ? 'dark'
      : 'light';
const esOscuro = () => temaApex() === 'dark';
const temaChart = () => (esOscuro() ? { theme: { mode: 'dark' }, tooltip: { theme: 'dark' } } : {});
const temaTooltip = () => (esOscuro() ? { theme: 'dark' } : {});

document.addEventListener('temaCambiado', (e) => {
  const tema = e.detail.theme === 'dark' ? 'dark' : 'light';
  [chartInstance, chartFlujo, chartCategorias, chartEstablecimientos].forEach((c) => {
    if (c) c.updateOptions({ theme: { mode: tema }, tooltip: { theme: tema } });
  });
});

let chartInstance = null;
let chartIngresos = [];
let chartEgresos = [];
let kpiTotal = KPI_TOTAL;
let kpiIngresos = KPI_INGRESOS;
let kpiEgresos = KPI_EGRESOS;
let kpiBalance = KPI_BALANCE;
let chartFlujo = null;
let chartCategorias = null;
let chartEstablecimientos = null;

function renderChartsAnaliticos() {
  const elFlujo = document.querySelector('#chart-flujo');
  if (elFlujo) {
    chartFlujo?.destroy();
    chartFlujo = new ApexCharts(elFlujo, {
      chart: { height: 280, type: 'line', toolbar: { show: false } },
      ...temaChart(),
      series: [{ name: 'Saldo acumulado', data: FLUJO_VALORES }],
      xaxis: { categories: FLUJO_ETIQUETAS },
      colors: ['#0d6efd'],
      stroke: { width: 2, curve: 'smooth' },
      markers: { size: 3 },
      yaxis: { labels: { formatter: value => dinero(value) } },
      tooltip: { ...temaTooltip(), y: { formatter: value => dinero(value) } },
    });
    chartFlujo.render().catch(() => {});
  }

  const elCategorias = document.querySelector('#chart-categorias');
  if (elCategorias) {
    chartCategorias?.destroy();
    const sinDatos = !CATEGORIAS_VALORES.length || CATEGORIAS_VALORES.every(v => !v);
    chartCategorias = new ApexCharts(elCategorias, {
      chart: { height: 280, type: 'pie', toolbar: { show: false } },
      ...temaChart(),
      series: sinDatos ? [1] : CATEGORIAS_VALORES,
      labels: sinDatos ? ['Sin egresos'] : CATEGORIAS_ETIQUETAS,
      legend: { position: 'bottom' },
      colors: ['#dc3545', '#fd7e14', '#ffc107', '#198754', '#0dcaf0'],
      dataLabels: { formatter: (val, opt) => `${opt.w.globals.labels[opt.seriesIndex]}: ${Math.round(val)}%` },
      tooltip: { ...temaTooltip(), y: { formatter: value => dinero(value) } },
    });
    chartCategorias.render().catch(() => {});
  }

  const elEst = document.querySelector('#chart-establecimientos');
  if (elEst) {
    chartEstablecimientos?.destroy();
    chartEstablecimientos = new ApexCharts(elEst, {
      chart: { height: 300, type: 'bar', toolbar: { show: false } },
      ...temaChart(),
      series: [
        { name: 'Ingresos', data: ESTABLECIMIENTOS_INGRESOS },
        { name: 'Egresos', data: ESTABLECIMIENTOS_EGRESOS },
      ],
      xaxis: { categories: ESTABLECIMIENTOS_ETIQUETAS },
      colors: ['#198754', '#dc3545'],
      dataLabels: { enabled: false },
      plotOptions: { bar: { horizontal: false, columnWidth: '50%' } },
      tooltip: { ...temaTooltip(), y: { formatter: value => dinero(value) } },
    });
    chartEstablecimientos.render().catch(() => {});
  }
}

function filaMovimientoHTML(m) {
  const esIngreso = m.tipo === 'Ingreso';
  return `<tr data-id="${m.id}" data-tipo="${m.tipo}" data-monto="${m.monto_total}" data-fecha="${m.fecha}" data-nombre="${m.nombre}" data-detalle="${m.detalle || ''}">
    <td>${m.fecha}</td>
    <td><span class="badge ${esIngreso ? 'text-bg-success' : 'text-bg-danger'}">${m.tipo}</span></td>
    <td>${m.nombre}</td>
    <td>${m.establecimiento || '—'}</td>
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
  const monto = row.children[5]?.textContent.trim() || '';
  document.getElementById('det-fecha').textContent = row.children[0].textContent.trim();
  document.getElementById('det-tipo').textContent = tipo;
  document.getElementById('det-nombre').textContent = row.children[2].textContent.trim();
  document.getElementById('det-detalle').textContent = row.children[4].textContent.trim();
  document.getElementById('det-monto').textContent = monto;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('modalVerMovimientoFinanciero')).show();
}

function abrirEdicionMovimiento(row) {
  document.getElementById('mov-id').value = row.dataset.id;
  document.getElementById('mov-fecha').value = row.dataset.fecha;
  document.getElementById('mov-tipo').value = row.dataset.tipo;
  document.getElementById('mov-monto').value = row.dataset.monto;
  document.getElementById('mov-nombre').value = row.children[2].textContent.trim();
  document.getElementById('mov-detalle').value = row.children[4].textContent.trim() === '-' ? '' : row.children[4].textContent.trim();
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

  const hayDatos = tbody.querySelector('tr[data-id]');
  let visibles = 0;
  tbody.querySelectorAll('tr[data-id]').forEach((row) => {
    const fecha = row.dataset.fecha || '';
    const nombre = (row.dataset.nombre || '').toLowerCase();
    const detalle = (row.children[4]?.textContent || '').toLowerCase();
    let mostrar = true;
    if (desde && fecha < desde) mostrar = false;
    if (hasta && fecha > hasta) mostrar = false;
    if (concepto && !(nombre.includes(concepto) || detalle.includes(concepto))) mostrar = false;
    row.style.display = mostrar ? '' : 'none';
    if (mostrar) visibles++;
  });

  const filaVacia = tbody.querySelector('#fila-vacia-movimientos');
  const filaFiltro = tbody.querySelector('.fila-filtro-vacio');
  if (hayDatos && visibles === 0) {
    if (filaVacia) filaVacia.style.display = 'none';
    if (!filaFiltro) {
      tbody.insertAdjacentHTML('beforeend', '<tr class="fila-filtro-vacio"><td colspan="7" class="text-center text-secondary py-4">No se encontraron movimientos para los filtros aplicados.</td></tr>');
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
  const idx = CHART_LABELS.indexOf(mesClave(fechaISO));
  if (idx === -1) return;
  const arr = tipo === 'Ingreso' ? chartIngresos : chartEgresos;
  arr[idx] = Number(arr[idx] || 0) + signo * Number(monto || 0);
  chartInstance.updateSeries([
    { name: 'Ingresos', data: chartIngresos.slice() },
    { name: 'Egresos', data: chartEgresos.slice() },
  ]);
}

document.addEventListener('DOMContentLoaded', function () {
  // Render chart
  chartIngresos = CHART_INGRESOS.slice();
  chartEgresos = CHART_EGRESOS.slice();
  try {
    chartInstance = new ApexCharts(document.querySelector('#chart-finanzas'), {
      chart: { height: 320, type: 'bar', toolbar: { show: false } },
      ...temaChart(),
      series: [
        { name: 'Ingresos', data: chartIngresos.slice() },
        { name: 'Egresos', data: chartEgresos.slice() },
      ],
      xaxis: { categories: CHART_LABELS },
      colors: ['#198754', '#dc3545'],
      dataLabels: { enabled: false },
      stroke: { show: true, width: 2, colors: ['transparent'] },
    });
    chartInstance.render().catch(() => {});
  } catch (e) {
    console.error('Error renderizando gráfico de finanzas', e);
  }

  renderChartsAnaliticos();

  // Form submit (crear o editar)
  const form = document.getElementById('form-registrar-mov-financiero');
  const modalRegistrar = document.getElementById('modalRegistrarMovimientoFinanciero');
  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      const id = document.getElementById('mov-id').value;
      const fd = new FormData(form);
      const url = id ? `/api/finanzas/movimientos/${id}/` : '/api/finanzas/movimientos/';
      enviarMovimiento(fd, url).then(res => res.json()).then(data => {
        if (data.error) {
          alert(data.error);
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
      document.getElementById('titulo-mov-modal').textContent = 'Editar movimiento financiero';
      form?.reset();
    });
  }

  // Eliminar (delegado para filas agregadas dinámicamente)
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
      if (!confirm('¿Dar de baja este movimiento financiero? Dejará de contabilizarse.')) return;
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
            tbody.innerHTML = '<tr id="fila-vacia-movimientos"><td colspan="7" class="text-center text-secondary py-4">No hay movimientos financieros registrados.</td></tr>';
          } else {
            aplicarFiltros();
          }
        } else {
          alert(data.error || 'No se pudo eliminar.');
        }
      }).catch(err => {
        console.error(err);
        alert('Error al eliminar movimiento.');
      });
    });
  }

  // Filtros de búsqueda
  ['filtro-desde', 'filtro-hasta', 'filtro-concepto'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', aplicarFiltros);
  });
  const btnLimpiar = document.getElementById('btn-limpiar-filtros');
  if (btnLimpiar) btnLimpiar.addEventListener('click', limpiarFiltros);
});
