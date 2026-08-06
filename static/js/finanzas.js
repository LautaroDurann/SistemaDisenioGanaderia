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

function filaMovimientoHTML(m) {
  const esIngreso = m.tipo === 'Ingreso';
  return `<tr data-id="${m.id}" data-tipo="${m.tipo}" data-monto="${m.monto_total}" data-fecha="${m.fecha}">
    <td>${m.fecha}</td>
    <td><span class="badge ${esIngreso ? 'text-bg-success' : 'text-bg-danger'}">${m.tipo}</span></td>
    <td>${m.nombre}</td>
    <td>${m.detalle || '-'}</td>
    <td class="text-end">${dinero(m.monto_total)}</td>
    <td class="text-end"><button class="btn btn-sm btn-outline-danger btn-eliminar" data-id="${m.id}">Eliminar</button></td>
  </tr>`;
}

function prependFila(movimiento) {
  const tbody = document.getElementById('tabla-finanzas-body');
  if (!tbody) return;
  const vacia = tbody.querySelector('tr td[colspan]');
  if (vacia) vacia.closest('tr').remove();
  tbody.insertAdjacentHTML('afterbegin', filaMovimientoHTML(movimiento));
}

function actualizarKPIs(tipo, monto, signo, fechaISO) {
  if (mesClave(fechaISO) !== mesActualClave()) return;
  const montoNum = Number(monto || 0);
  const esIngreso = tipo === 'Ingreso';
  const kpiTotal = document.getElementById('kpi-total');
  const kpiTipo = document.getElementById(esIngreso ? 'kpi-ingresos' : 'kpi-egresos');
  const kpiBalance = document.getElementById('kpi-balance');
  if (kpiTotal) kpiTotal.textContent = Number(kpiTotal.textContent) + signo;
  if (kpiTipo) kpiTipo.textContent = dinero(Number(kpiTipo.textContent.replace(/[^\d.-]/g, '')) + signo * montoNum);
  if (kpiBalance) kpiBalance.textContent = dinero(Number(kpiBalance.textContent.replace(/[^\d.-]/g, '')) + signo * (esIngreso ? 1 : -1) * montoNum);
}

function actualizarChart(tipo, monto, signo, fechaISO) {
  if (!chartInstance) return;
  const idx = CHART_LABELS.indexOf(mesClave(fechaISO));
  if (idx === -1) return;
  const series = [
    { name: 'Ingresos', data: CHART_INGRESOS.slice() },
    { name: 'Egresos', data: CHART_EGRESOS.slice() },
  ];
  const arr = tipo === 'Ingreso' ? series[0].data : series[1].data;
  arr[idx] = Number(arr[idx]) + signo * Number(monto || 0);
  chartInstance.updateSeries(series);
}

document.addEventListener('DOMContentLoaded', function () {
  // Render chart
  try {
    chartInstance = new ApexCharts(document.querySelector('#chart-finanzas'), {
      chart: { height: 320, type: 'bar', toolbar: { show: false } },
      series: [
        { name: 'Ingresos', data: CHART_INGRESOS },
        { name: 'Egresos', data: CHART_EGRESOS },
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

  // Form submit
  const form = document.getElementById('form-registrar-mov-financiero');
  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      const fd = new FormData(form);
      fetch('/api/finanzas/movimientos/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: fd,
      }).then(res => res.json()).then(data => {
        if (data.error) {
          alert(data.error);
          return;
        }
        prependFila(data.movimiento);
        actualizarKPIs(data.movimiento.tipo, data.movimiento.monto_total, 1, data.movimiento.fecha);
        actualizarChart(data.movimiento.tipo, data.movimiento.monto_total, 1, data.movimiento.fecha);
        form.reset();
        bootstrap.Modal.getInstance(document.getElementById('modalRegistrarMovimientoFinanciero'))?.hide();
      }).catch(err => {
        console.error(err);
        alert('Error al crear movimiento.');
      });
    });
  }

  // Eliminar (delegado para filas agregadas dinámicamente)
  const tbody = document.getElementById('tabla-finanzas-body');
  if (tbody) {
    tbody.addEventListener('click', function (e) {
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
          if (!tbody.querySelector('tr')) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-4">No hay movimientos financieros registrados.</td></tr>';
          }
        } else {
          alert('No se pudo eliminar.');
        }
      }).catch(err => {
        console.error(err);
        alert('Error al eliminar movimiento.');
      });
    });
  }
});
