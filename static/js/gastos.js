(() => {
  const data = window.HUACAPP_DATA || {};
  let compras = data.compras || [];
  let proveedores = data.proveedores || [];
  let insumos = data.insumos || [];
  let liquidaciones = data.liquidaciones || [];
  let empleados = data.empleados || [];
  let modalCompra;
  let modalProveedor;
  let modalLiquidacion;
  let chartGastos;
  let chartSueldos;
  let gastosLabels = [];
  let comprasSeries = [];
  let sueldosSeries = [];
  let sueldosChartLabels = [];
  let sueldosChartSeries = [];
  const $ = (id) => document.getElementById(id);
  const dinero = (valor) => `$ ${Number(valor || 0).toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  const fechaHoy = () => new Date().toISOString().slice(0, 10);
  const csrf = () => document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.split('=')[1] || '';
  const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#039;'}[c]));

  function mostrar(texto, tipo) {
    const contenedor = $('mensaje-gastos');
    if (!contenedor) return;
    contenedor.innerHTML = `<div class="alert alert-${tipo}">${escapeHtml(texto)}</div>`;
  }

  function actualizarSerie(serie, labels, fechaISO, monto, signo) {
    const idx = labels.indexOf(String(fechaISO || '').slice(0, 4));
    if (idx === -1) return;
    serie[idx] = Number(serie[idx] || 0) + signo * Number(monto || 0);
  }

  // ----------------------------- Compras -----------------------------

  function detalleCompra(c) {
    if (c.lote) {
      return `${escapeHtml(c.lote.insumo_nombre || 'Insumo')} - ${c.lote.cantidad} u. (Lote ${escapeHtml(c.lote.lote_nombre)})`;
    }
    if (c.animal) {
      return `${escapeHtml(c.animal.tipo_animal)} ${escapeHtml(c.animal.sexo)} - #${escapeHtml(c.animal.caravana)} ${escapeHtml(c.animal.nombre)}`;
    }
    return escapeHtml(c.detalle) || '-';
  }

  function renderCompras() {
    $('compras-body').innerHTML = compras.map(c => `
      <tr>
        <td>${escapeHtml(c.fecha)}</td>
        <td>${escapeHtml(c.tipo)}</td>
        <td>${escapeHtml(c.proveedor)}</td>
        <td>${detalleCompra(c)}</td>
        <td>${escapeHtml(c.establecimiento || '—')}</td>
        <td class="text-end">${dinero(c.monto_total)}</td>
        <td>${escapeHtml(c.metodo_de_pago)}</td>
        <td><span class="badge ${c.estado_de_pago === 'Pagada' ? 'text-bg-success' : 'text-bg-warning'}">${escapeHtml(c.estado_de_pago)}</span></td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary editar-compra" data-id="${c.id}"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger eliminar-compra" data-id="${c.id}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="9" class="text-center text-secondary py-4">Todavía no hay compras registradas.</td></tr>';

    document.querySelectorAll('.editar-compra').forEach(b => b.onclick = () => abrirEdicionCompra(Number(b.dataset.id)));
    document.querySelectorAll('.eliminar-compra').forEach(b => b.onclick = () => eliminarCompra(Number(b.dataset.id)));
  }

  function renderMontosTipo() {
    const tbody = $('montos-tipo-body');
    if (!tbody) return;
    const anio = String(new Date().getFullYear());
    const delAnio = compras.filter(c => String(c.fecha || '').startsWith(anio));
    const porTipo = {};
    delAnio.forEach(c => {
      porTipo[c.tipo] = (porTipo[c.tipo] || 0) + Number(c.monto_total || 0);
    });
    const tipos = ['Insumos', 'Animales', 'Maquinaria', 'Otros'];
    tbody.innerHTML = tipos.map(t => `
      <tr>
        <td>${escapeHtml(t)}</td>
        <td class="text-end">${dinero(porTipo[t] || 0)}</td>
      </tr>`).join('');
  }

  function renderProveedores() {
    const tbody = $('proveedores-body');
    if (!tbody) return;
    tbody.innerHTML = proveedores.map(p => `
      <tr>
        <td>${escapeHtml(p.nombre)}</td>
        <td>${escapeHtml(p.correo || '-')}</td>
        <td>${escapeHtml(p.telefono || '-')}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary editar-proveedor" data-id="${p.id}"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger eliminar-proveedor" data-id="${p.id}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="4" class="text-center text-secondary py-3">No hay proveedores cargados.</td></tr>';

    document.querySelectorAll('.editar-proveedor').forEach(btn => btn.onclick = () => abrirEdicionProveedor(Number(btn.dataset.id)));
    document.querySelectorAll('.eliminar-proveedor').forEach(btn => btn.onclick = () => eliminarProveedor(Number(btn.dataset.id)));
  }

  // ----------------------------- Sueldos -----------------------------

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
          <button class="btn btn-sm btn-outline-primary editar-liquidacion" data-id="${c.id}"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger eliminar-liquidacion" data-id="${c.id}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="7" class="text-center text-secondary py-4">Todavía no hay liquidaciones registradas.</td></tr>';

    document.querySelectorAll('.editar-liquidacion').forEach(b => b.onclick = () => abrirEdicionLiquidacion(Number(b.dataset.id)));
    document.querySelectorAll('.eliminar-liquidacion').forEach(b => b.onclick = () => eliminarLiquidacion(Number(b.dataset.id)));
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

  // ----------------------------- KPIs y gráficos -----------------------------

  function renderSummary() {
    const summary = data.summary || {};
    $('kpi-total-gastos').textContent = summary.total_gastos || 0;
    $('kpi-egresos-total').textContent = dinero(summary.egresos_total || 0);
    $('kpi-egresos-anio').textContent = dinero(summary.egresos_anio_actual || 0);
    $('kpi-proveedores').textContent = summary.proveedores || 0;
  }

  function renderCharts() {
    const chartGastosEl = $('chart-gastos');
    if (chartGastosEl) {
      chartGastos?.destroy();
      chartGastos = new ApexCharts(chartGastosEl, {
        chart: { type: 'bar', height: 320, stacked: true, toolbar: { show: false } },
        series: [
          { name: 'Compras', data: comprasSeries },
          { name: 'Sueldos', data: sueldosSeries },
        ],
        xaxis: { categories: gastosLabels },
        colors: ['#dc3545', '#fd7e14'],
        dataLabels: { enabled: false },
        tooltip: { y: { formatter: value => dinero(value) } },
        legend: { position: 'top' },
      });
      chartGastos.render();
    }

    const chartSueldosEl = $('chart-sueldos');
    if (chartSueldosEl) {
      chartSueldos?.destroy();
      chartSueldos = new ApexCharts(chartSueldosEl, {
        chart: { type: 'bar', height: 320, toolbar: { show: false } },
        series: [{ name: 'Sueldos', data: sueldosChartSeries }],
        xaxis: { categories: sueldosChartLabels },
        colors: ['#fd7e14'],
        dataLabels: { enabled: false },
        tooltip: { y: { formatter: value => dinero(value) } },
      });
      chartSueldos.render();
    }
  }

  function renderTodo() {
    renderSummary();
    renderProveedores();
    renderCompras();
    renderMontosTipo();
    renderEmpleados();
    renderLiquidaciones();
    renderCharts();
  }

  // ----------------------------- Modal compra -----------------------------

  function setTipoPanel(tipo) {
    $('panel-insumos').classList.toggle('d-none', tipo !== 'Insumos');
    $('panel-animales').classList.toggle('d-none', tipo !== 'Animales');
    $('grupo-monto-generico').classList.toggle('d-none', tipo === 'Insumos' || tipo === 'Animales');
  }

  function filtrarInsumos() {
    const tipoFiltro = $('compra-tipo-insumo').value;
    const select = $('compra-insumo');
    const actual = select.value;
    select.innerHTML = '<option value="">— Elegí un insumo —</option>' +
      insumos.filter(i => !tipoFiltro || i.tipo === tipoFiltro)
        .map(i => `<option value="${i.id}" data-tipo="${escapeHtml(i.tipo)}">${escapeHtml(i.nombre)}</option>`).join('');
    if (actual && [...select.options].some(o => o.value === actual)) select.value = actual;
  }

  function actualizarMontoInsumos() {
    const cantidad = Number($('compra-cantidad').value || 0);
    const precio = Number($('compra-precio-unitario').value || 0);
    $('compra-monto-insumos').value = (cantidad * precio).toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function abrirNuevaCompra() {
    $('form-compra').reset();
    $('compra-id').value = '';
    $('compra-fecha').value = fechaHoy();
    $('compra-tipo').value = 'Insumos';
    $('compra-tipo-insumo').value = '';
    $('compra-nuevo-insumo').checked = false;
    $('grupo-nuevo-insumo').classList.add('d-none');
    $('titulo-compra').textContent = 'Registrar compra';
    setTipoPanel('Insumos');
    filtrarInsumos();
    actualizarMontoInsumos();
    modalCompra.show();
  }

  function abrirEdicionCompra(id) {
    const c = compras.find(x => x.id === id);
    if (!c) return;
    $('compra-id').value = id;
    $('compra-fecha').value = c.fecha;
    $('compra-proveedor').value = c.proveedor_id || '';
    $('compra-detalle').value = c.detalle;
    $('compra-tipo').value = c.tipo;
    $('compra-metodo').value = c.metodo_de_pago || 'Efectivo';
    $('compra-estado').value = c.estado_de_pago || 'Pendiente';
    setTipoPanel(c.tipo);
    $('titulo-compra').textContent = `Editar compra #${id}`;

    if (c.tipo === 'Insumos') {
      const lote = c.lote || {};
      $('compra-tipo-insumo').value = lote.insumo_tipo || '';
      filtrarInsumos();
      const insumoExistente = insumos.some(i => i.id === Number(lote.insumo_id));
      if (insumoExistente) {
        $('compra-nuevo-insumo').checked = false;
        $('grupo-nuevo-insumo').classList.add('d-none');
        $('compra-insumo').value = lote.insumo_id;
      } else {
        $('compra-nuevo-insumo').checked = true;
        $('grupo-nuevo-insumo').classList.remove('d-none');
        $('compra-nuevo-insumo-nombre').value = lote.insumo_nombre || '';
      }
      $('compra-lote-nombre').value = lote.lote_nombre || '';
      $('compra-fecha-vencimiento').value = lote.fecha_vencimiento || '';
      $('compra-cantidad').value = lote.cantidad || '';
      $('compra-precio-unitario').value = lote.precio_unitario || '';
      actualizarMontoInsumos();
    } else if (c.tipo === 'Animales') {
      const animal = c.animal || {};
      $('compra-caravana').value = animal.caravana || '';
      $('compra-animal-nombre').value = animal.nombre || '';
      $('compra-tipo-animal').value = animal.tipo_animal || 'Bovino';
      $('compra-sexo').value = animal.sexo || 'Hembra';
      $('compra-raza').value = animal.raza || '';
      $('compra-color').value = animal.color || '';
      $('compra-fecha-nacimiento').value = animal.fecha_nacimiento || '';
      $('compra-peso-nacer').value = animal.peso_al_nacer || '';
      $('compra-peso-actual').value = animal.peso_actual || '';
      $('compra-monto-animal').value = c.monto_total;
      $('compra-detalle-animal').value = animal.detalle || '';
    } else {
      $('compra-monto-total').value = c.monto_total;
    }
    modalCompra.show();
  }

  async function eliminarCompra(id) {
    if (!confirm('¿Eliminar la compra? Se quitará el movimiento financiero y el lote/animal asociado.')) return;
    const r = await fetch(`/api/compras/${id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    if (!r.ok) return mostrar('No se pudo eliminar la compra.', 'danger');
    const compra = compras.find(c => c.id === id);
    if (compra) {
      compras = compras.filter(c => c.id !== id);
      const summary = data.summary = data.summary || {};
      const monto = Number(compra.monto_total || 0);
      const esAnioActual = String(compra.fecha || '').slice(0, 4) === String(new Date().getFullYear());
      summary.total_compras = Math.max(0, Number(summary.total_compras || 0) - 1);
      summary.total_gastos = Math.max(0, Number(summary.total_gastos || 0) - 1);
      summary.egresos_total = Math.max(0, Number(summary.egresos_total || 0) - monto);
      if (esAnioActual) {
        summary.egresos_anio_actual = Math.max(0, Number(summary.egresos_anio_actual || 0) - monto);
      }
      actualizarSerie(comprasSeries, gastosLabels, compra.fecha, monto, -1);
    }
    renderCompras();
    renderMontosTipo();
    renderSummary();
    renderCharts();
    mostrar('Compra eliminada.', 'success');
  }

  function datosInsumo() {
    const esNuevo = $('compra-nuevo-insumo').checked;
    return {
      insumo_id: esNuevo ? '' : $('compra-insumo').value,
      tipo_insumo: $('compra-tipo-insumo').value,
      nuevo_insumo: esNuevo ? $('compra-nuevo-insumo-nombre').value : '',
    };
  }

  // ----------------------------- Modal proveedor -----------------------------

  function abrirEdicionProveedor(id) {
    const proveedor = proveedores.find(p => p.id === id);
    if (!proveedor) return;
    $('proveedor-id').value = proveedor.id;
    $('titulo-proveedor').textContent = 'Editar proveedor';
    const form = $('form-proveedor');
    form.elements.dni.value = proveedor.dni || '';
    form.elements.nombre.value = proveedor.nombre || '';
    form.elements.apellido.value = proveedor.apellido || '';
    form.elements.correo_electronico.value = proveedor.correo || '';
    form.elements.fecha_nacimiento.value = proveedor.fecha_nacimiento || '';
    form.elements.telefono.value = proveedor.telefono || '';
    modalProveedor.show();
  }

  async function eliminarProveedor(id) {
    if (!confirm('¿Eliminar este proveedor?')) return;
    const r = await fetch(`/api/proveedores/${id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    if (!r.ok) return mostrar('No se pudo eliminar el proveedor.', 'danger');
    proveedores = proveedores.filter(p => p.id !== id);
    data.summary = data.summary || {};
    data.summary.proveedores = Math.max(0, Number(data.summary.proveedores || 0) - 1);
    renderProveedores();
    renderSummary();
    mostrar('Proveedor eliminado.', 'success');
  }

  // ----------------------------- Modal liquidación -----------------------------

  function abrirNuevaLiquidacion() {
    $('form-liquidacion').reset();
    $('liquidacion-id').value = '';
    $('liquidacion-fecha').value = fechaHoy();
    $('liquidacion-empleado').value = '';
    $('titulo-liquidacion').textContent = 'Registrar liquidación';
    modalLiquidacion.show();
  }

  function abrirEdicionLiquidacion(id) {
    const c = liquidaciones.find(x => x.id === id);
    if (!c) return;
    $('liquidacion-id').value = id;
    $('liquidacion-fecha').value = c.fecha;
    $('liquidacion-empleado').value = c.empleado_id || '';
    $('liquidacion-sueldo').value = c.sueldo;
    $('liquidacion-descripcion').value = c.descripcion || '';
    $('titulo-liquidacion').textContent = `Editar liquidación #${id}`;
    modalLiquidacion.show();
  }

  async function eliminarLiquidacion(id) {
    if (!confirm('¿Eliminar la liquidación? Se quitará también el egreso registrado en Finanzas.')) return;
    const r = await fetch(`/api/liquidaciones/${id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    if (!r.ok) return mostrar('No se pudo eliminar la liquidación.', 'danger');
    const liquidacion = liquidaciones.find(c => c.id === id);
    if (liquidacion) {
      liquidaciones = liquidaciones.filter(c => c.id !== id);
      const summary = data.summary = data.summary || {};
      const monto = Number(liquidacion.sueldo || 0);
      const esAnioActual = String(liquidacion.fecha || '').slice(0, 4) === String(new Date().getFullYear());
      summary.total_liquidaciones = Math.max(0, Number(summary.total_liquidaciones || 0) - 1);
      summary.total_gastos = Math.max(0, Number(summary.total_gastos || 0) - 1);
      summary.total_sueldos = Math.max(0, Number(summary.total_sueldos || 0) - monto);
      summary.egresos_total = Math.max(0, Number(summary.egresos_total || 0) - monto);
      if (esAnioActual) {
        summary.sueldos_anio_actual = Math.max(0, Number(summary.sueldos_anio_actual || 0) - monto);
        summary.egresos_anio_actual = Math.max(0, Number(summary.egresos_anio_actual || 0) - monto);
      }
      actualizarSerie(sueldosSeries, gastosLabels, liquidacion.fecha, monto, -1);
      actualizarSerie(sueldosChartSeries, sueldosChartLabels, liquidacion.fecha, monto, -1);
    }
    renderLiquidaciones();
    renderSummary();
    renderCharts();
    mostrar('Liquidación eliminada.', 'success');
  }

  // ----------------------------- Init -----------------------------

  document.addEventListener('DOMContentLoaded', () => {
    modalCompra = new bootstrap.Modal($('modalCompra'));
    modalProveedor = new bootstrap.Modal($('modalProveedor'));
    modalLiquidacion = new bootstrap.Modal($('modalLiquidacion'));

    const chartGastosData = data.chart_gastos || {};
    gastosLabels = chartGastosData.labels_json ? JSON.parse(chartGastosData.labels_json) : [];
    comprasSeries = chartGastosData.compras_json ? JSON.parse(chartGastosData.compras_json) : [];
    sueldosSeries = chartGastosData.sueldos_json ? JSON.parse(chartGastosData.sueldos_json) : [];
    const chartSueldosData = data.chart_sueldos || {};
    sueldosChartLabels = chartSueldosData.labels_json ? JSON.parse(chartSueldosData.labels_json) : [];
    sueldosChartSeries = chartSueldosData.series_json ? JSON.parse(chartSueldosData.series_json) : [];

    renderTodo();

    if ($('nueva-compra')) $('nueva-compra').onclick = abrirNuevaCompra;
    if ($('nueva-compra-tabla')) $('nueva-compra-tabla').onclick = abrirNuevaCompra;
    if ($('nueva-liquidacion')) $('nueva-liquidacion').onclick = abrirNuevaLiquidacion;
    if ($('nueva-liquidacion-tabla')) $('nueva-liquidacion-tabla').onclick = abrirNuevaLiquidacion;
    if ($('nuevo-proveedor')) $('nuevo-proveedor').onclick = () => {
      $('form-proveedor').reset();
      $('proveedor-id').value = '';
      $('titulo-proveedor').textContent = 'Nuevo proveedor';
      modalProveedor.show();
    };

    $('compra-tipo').addEventListener('change', e => setTipoPanel(e.target.value));
    $('compra-tipo-insumo').addEventListener('change', filtrarInsumos);
    $('compra-nuevo-insumo').addEventListener('change', e => {
      $('grupo-nuevo-insumo').classList.toggle('d-none', !e.target.checked);
    });
    ['compra-cantidad', 'compra-precio-unitario'].forEach(id => $(id).addEventListener('input', actualizarMontoInsumos));

    $('form-compra').addEventListener('submit', async e => {
      e.preventDefault();
      const form = new FormData(e.target);
      const id = $('compra-id').value;
      const tipo = $('compra-tipo').value;

      if (tipo === 'Insumos') {
        const datosInsumoForm = datosInsumo();
        form.append('insumo_id', datosInsumoForm.insumo_id);
        form.append('tipo_insumo', datosInsumoForm.tipo_insumo);
        form.append('nuevo_insumo', datosInsumoForm.nuevo_insumo);
        form.append('lote_nombre', $('compra-lote-nombre').value);
        form.append('fecha_vencimiento', $('compra-fecha-vencimiento').value);
        form.append('cantidad', $('compra-cantidad').value);
        form.append('precio_unitario', $('compra-precio-unitario').value);
      }
      if (tipo === 'Animales') {
        form.set('monto_total', $('compra-monto-animal').value);
        form.append('costo_adquisicion', $('compra-monto-animal').value);
        form.append('descripcion', $('compra-detalle-animal').value);
      }
      if (tipo !== 'Insumos' && tipo !== 'Animales') {
        form.set('monto_total', $('compra-monto-total').value);
      }

      const r = await fetch(id ? `/api/compras/${id}/` : '/api/compras/', { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form });
      const respuesta = await r.json();
      if (!r.ok) return mostrar(respuesta.error || 'No se pudo guardar la compra.', 'danger');
      const compraData = respuesta.compra;
      const montoNuevo = Number(compraData.monto_total || 0);
      const anioActual = String(new Date().getFullYear());
      const esNueva = !id;
      const summary = data.summary = data.summary || {};

      if (esNueva) {
        compras.unshift(compraData);
        summary.total_compras = Number(summary.total_compras || 0) + 1;
        summary.total_gastos = Number(summary.total_gastos || 0) + 1;
        summary.egresos_total = Number(summary.egresos_total || 0) + montoNuevo;
        if (String(compraData.fecha || '').slice(0, 4) === anioActual) {
          summary.egresos_anio_actual = Number(summary.egresos_anio_actual || 0) + montoNuevo;
        }
        actualizarSerie(comprasSeries, gastosLabels, compraData.fecha, montoNuevo, 1);
      } else {
        const idx = compras.findIndex(c => c.id === Number(id));
        const vieja = idx !== -1 ? compras[idx] : null;
        if (vieja) {
          const montoViejo = Number(vieja.monto_total || 0);
          summary.egresos_total = Math.max(0, Number(summary.egresos_total || 0) - montoViejo + montoNuevo);
          if (String(vieja.fecha || '').slice(0, 4) === anioActual) {
            summary.egresos_anio_actual = Math.max(0, Number(summary.egresos_anio_actual || 0) - montoViejo);
          }
          actualizarSerie(comprasSeries, gastosLabels, vieja.fecha, montoViejo, -1);
          compras[idx] = compraData;
        }
        if (String(compraData.fecha || '').slice(0, 4) === anioActual) {
          summary.egresos_anio_actual = Number(summary.egresos_anio_actual || 0) + montoNuevo;
        }
        actualizarSerie(comprasSeries, gastosLabels, compraData.fecha, montoNuevo, 1);
      }
      renderCompras();
      renderMontosTipo();
      renderSummary();
      renderCharts();
      modalCompra.hide();
      mostrar('Compra guardada.', 'success');
    });

    $('form-proveedor').addEventListener('submit', async e => {
      e.preventDefault();
      const form = new FormData(e.target);
      const dni = String(form.get('dni') || '').trim();
      if (dni && (dni.length < 7 || dni.length > 8)) {
        alert('El DNI debe tener entre 7 y 8 caracteres.');
        return;
      }
      const proveedorId = $('proveedor-id').value;
      const url = proveedorId ? `/api/proveedores/${proveedorId}/` : '/api/proveedores/';
      const r = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form });
      const respuesta = await r.json();
      if (!r.ok) return alert(respuesta.error || 'No se pudo guardar el proveedor.');
      if (proveedorId) {
        const idx = proveedores.findIndex(p => p.id === Number(proveedorId));
        if (idx !== -1) proveedores[idx] = respuesta.proveedor;
      } else {
        proveedores.push(respuesta.proveedor);
        data.summary = data.summary || {};
        data.summary.proveedores = Number(data.summary.proveedores || 0) + 1;
      }
      renderProveedores();
      renderSummary();
      modalProveedor.hide();
      mostrar('Proveedor guardado.', 'success');
    });

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
      const summary = data.summary = data.summary || {};

      if (esNueva) {
        liquidaciones.unshift(liquidacionData);
        summary.total_liquidaciones = Number(summary.total_liquidaciones || 0) + 1;
        summary.total_gastos = Number(summary.total_gastos || 0) + 1;
        summary.total_sueldos = Number(summary.total_sueldos || 0) + montoNuevo;
        summary.egresos_total = Number(summary.egresos_total || 0) + montoNuevo;
        if (String(liquidacionData.fecha || '').slice(0, 4) === anioActual) {
          summary.sueldos_anio_actual = Number(summary.sueldos_anio_actual || 0) + montoNuevo;
          summary.egresos_anio_actual = Number(summary.egresos_anio_actual || 0) + montoNuevo;
        }
        actualizarSerie(sueldosSeries, gastosLabels, liquidacionData.fecha, montoNuevo, 1);
        actualizarSerie(sueldosChartSeries, sueldosChartLabels, liquidacionData.fecha, montoNuevo, 1);
      } else {
        const idx = liquidaciones.findIndex(c => c.id === Number(id));
        const vieja = idx !== -1 ? liquidaciones[idx] : null;
        if (vieja) {
          const montoViejo = Number(vieja.sueldo || 0);
          summary.total_sueldos = Math.max(0, Number(summary.total_sueldos || 0) - montoViejo + montoNuevo);
          summary.egresos_total = Math.max(0, Number(summary.egresos_total || 0) - montoViejo + montoNuevo);
          if (String(vieja.fecha || '').slice(0, 4) === anioActual) {
            summary.sueldos_anio_actual = Math.max(0, Number(summary.sueldos_anio_actual || 0) - montoViejo);
            summary.egresos_anio_actual = Math.max(0, Number(summary.egresos_anio_actual || 0) - montoViejo);
          }
          actualizarSerie(sueldosSeries, gastosLabels, vieja.fecha, montoViejo, -1);
          actualizarSerie(sueldosChartSeries, sueldosChartLabels, vieja.fecha, montoViejo, -1);
          liquidaciones[idx] = liquidacionData;
        }
        if (String(liquidacionData.fecha || '').slice(0, 4) === anioActual) {
          summary.sueldos_anio_actual = Number(summary.sueldos_anio_actual || 0) + montoNuevo;
          summary.egresos_anio_actual = Number(summary.egresos_anio_actual || 0) + montoNuevo;
        }
        actualizarSerie(sueldosSeries, gastosLabels, liquidacionData.fecha, montoNuevo, 1);
        actualizarSerie(sueldosChartSeries, sueldosChartLabels, liquidacionData.fecha, montoNuevo, 1);
      }
      renderLiquidaciones();
      renderSummary();
      renderCharts();
      modalLiquidacion.hide();
      mostrar('Liquidación guardada.', 'success');
    });
  });
})();
