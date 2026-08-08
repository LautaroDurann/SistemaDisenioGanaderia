(() => {
  const data = window.GANASTOCK_DATA || {};
  let liquidaciones = data.liquidaciones || [];
  let empleados = data.empleados || [];
  let modal;
  let chartInstance;
  let chartLabels = [];
  let chartSeries = [];
  const $ = (id) => document.getElementById(id);
  const dinero = (valor) => `$ ${Number(valor || 0).toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  const fechaHoy = () => new Date().toISOString().slice(0, 10);
  const csrf = () => document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.split('=')[1] || '';
  const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#039;'}[c]));

  function mostrar(texto, tipo) {
    const contenedor = $('mensaje-sueldo');
    if (!contenedor) return;
    contenedor.innerHTML = `<div class="alert alert-${tipo}">${escapeHtml(texto)}</div>`;
  }

  function renderLiquidaciones() {
    $('liquidaciones-body').innerHTML = liquidaciones.map(c => `
      <tr>
        <td>${escapeHtml(c.fecha)}</td>
        <td>${escapeHtml(c.empleado)}</td>
        <td>${escapeHtml(c.empleado_usuario)}</td>
        <td>${escapeHtml(c.establecimiento || '—')}</td>
        <td>${escapeHtml(c.descripcion) || '-'}</td>
        <td class="text-end">${dinero(c.sueldo)}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary editar" data-id="${c.id}"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger eliminar" data-id="${c.id}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="7" class="text-center text-secondary py-4">Todavía no hay liquidaciones registradas.</td></tr>';

    document.querySelectorAll('.editar').forEach(b => b.onclick = () => abrirEdicion(Number(b.dataset.id)));
    document.querySelectorAll('.eliminar').forEach(b => b.onclick = () => eliminarLiquidacion(Number(b.dataset.id)));
  }

  function renderEmpleados() {
    const tbody = $('empleados-body');
    if (!tbody) return;
    tbody.innerHTML = empleados.map(e => `
      <tr>
        <td>${escapeHtml(e.nombre)}</td>
        <td>@${escapeHtml(e.usuario)}</td>
      </tr>`).join('') || '<tr><td colspan="2" class="text-center text-secondary py-4">No hay empleados cargados.</td></tr>';
  }

  function renderSummary() {
    const summary = data.summary || {};
    $('kpi-total-liquidaciones').textContent = summary.total_liquidaciones || 0;
    $('kpi-total-sueldos').textContent = dinero(summary.total_sueldos || 0);
    $('kpi-sueldos-anio').textContent = dinero(summary.total_anio_actual || 0);
    $('kpi-empleados').textContent = summary.empleados || 0;
  }

  function renderChart() {
    const chartEl = $('chart-sueldos');
    if (!chartEl) return;
    const chartData = data.chart || {};
    chartLabels = chartData.labels_json ? JSON.parse(chartData.labels_json) : [];
    chartSeries = chartData.series_json ? JSON.parse(chartData.series_json) : [];
    chartInstance?.destroy();
    chartInstance = new ApexCharts(chartEl, {
      chart: { type: 'bar', height: 320, toolbar: { show: false } },
      series: [{ name: 'Sueldos', data: chartSeries }],
      xaxis: { categories: chartLabels },
      colors: ['#fd7e14'],
      dataLabels: { enabled: false },
      tooltip: { y: { formatter: value => dinero(value) } },
    });
    chartInstance.render();
  }

  function actualizarChartAnio(fechaISO, monto, signo) {
    const idx = chartLabels.indexOf(String(fechaISO || '').slice(0, 4));
    if (idx === -1) return;
    chartSeries[idx] = Number(chartSeries[idx] || 0) + signo * Number(monto || 0);
  }

  function abrirNueva() {
    $('form-liquidacion').reset();
    $('liquidacion-id').value = '';
    $('liquidacion-fecha').value = fechaHoy();
    $('liquidacion-empleado').value = '';
    $('titulo-liquidacion').textContent = 'Registrar liquidación';
    modal.show();
  }

  function abrirEdicion(id) {
    const c = liquidaciones.find(x => x.id === id);
    if (!c) return;
    $('liquidacion-id').value = id;
    $('liquidacion-fecha').value = c.fecha;
    $('liquidacion-empleado').value = c.empleado_id || '';
    $('liquidacion-sueldo').value = c.sueldo;
    $('liquidacion-descripcion').value = c.descripcion || '';
    $('titulo-liquidacion').textContent = `Editar liquidación #${id}`;
    modal.show();
  }

  async function eliminarLiquidacion(id) {
    if (!confirm('¿Eliminar la liquidación? Se quitará también el egreso registrado en Finanzas.')) return;
    const r = await fetch(`/api/liquidaciones/${id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    if (!r.ok) return mostrar('No se pudo eliminar la liquidación.', 'danger');
    const liquidacion = liquidaciones.find(c => c.id === id);
    if (liquidacion) {
      liquidaciones = liquidaciones.filter(c => c.id !== id);
      data.summary = data.summary || {};
      data.summary.total_liquidaciones = Math.max(0, Number(data.summary.total_liquidaciones || 0) - 1);
      const monto = Number(liquidacion.sueldo || 0);
      data.summary.total_sueldos = Math.max(0, Number(data.summary.total_sueldos || 0) - monto);
      if (String(liquidacion.fecha || '').slice(0, 4) === String(new Date().getFullYear())) {
        data.summary.total_anio_actual = Math.max(0, Number(data.summary.total_anio_actual || 0) - monto);
      }
      actualizarChartAnio(liquidacion.fecha, monto, -1);
    }
    renderLiquidaciones();
    renderSummary();
    renderChart();
    mostrar('Liquidación eliminada.', 'success');
  }

  document.addEventListener('DOMContentLoaded', () => {
    modal = new bootstrap.Modal($('modalLiquidacion'));

    renderSummary();
    renderEmpleados();
    renderChart();
    renderLiquidaciones();

    $('nueva-liquidacion').onclick = abrirNueva;
    $('nueva-liquidacion-tabla').onclick = abrirNueva;

    $('form-liquidacion').addEventListener('submit', async e => {
      e.preventDefault();
      const form = new FormData(e.target);
      const id = $('liquidacion-id').value;

      const r = await fetch(id ? `/api/liquidaciones/${id}/` : '/api/liquidaciones/', { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form });
      const respuesta = await r.json();
      if (!r.ok) return mostrar(respuesta.error || 'No se pudo guardar la liquidación.', 'danger');
      const liquidacionData = respuesta.liquidacion;
      const montoNuevo = Number(liquidacionData.sueldo || 0);
      const anioActual = String(new Date().getFullYear());
      const esNueva = !id;

      data.summary = data.summary || {};
      if (esNueva) {
        liquidaciones.unshift(liquidacionData);
        data.summary.total_liquidaciones = Number(data.summary.total_liquidaciones || 0) + 1;
        data.summary.total_sueldos = Number(data.summary.total_sueldos || 0) + montoNuevo;
        if (String(liquidacionData.fecha || '').slice(0, 4) === anioActual) {
          data.summary.total_anio_actual = Number(data.summary.total_anio_actual || 0) + montoNuevo;
        }
        actualizarChartAnio(liquidacionData.fecha, montoNuevo, 1);
      } else {
        const idx = liquidaciones.findIndex(c => c.id === Number(id));
        const vieja = idx !== -1 ? liquidaciones[idx] : null;
        if (vieja) {
          const montoViejo = Number(vieja.sueldo || 0);
          data.summary.total_sueldos = Math.max(0, Number(data.summary.total_sueldos || 0) - montoViejo + montoNuevo);
          if (String(vieja.fecha || '').slice(0, 4) === anioActual) {
            data.summary.total_anio_actual = Math.max(0, Number(data.summary.total_anio_actual || 0) - montoViejo);
          }
          actualizarChartAnio(vieja.fecha, montoViejo, -1);
          liquidaciones[idx] = liquidacionData;
        }
        if (String(liquidacionData.fecha || '').slice(0, 4) === anioActual) {
          data.summary.total_anio_actual = Number(data.summary.total_anio_actual || 0) + montoNuevo;
        }
        actualizarChartAnio(liquidacionData.fecha, montoNuevo, 1);
      }
      renderLiquidaciones();
      renderSummary();
      renderChart();
      modal.hide();
      mostrar('Liquidación guardada.', 'success');
    });
  });
})();
