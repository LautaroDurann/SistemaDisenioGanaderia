(() => {
  const data = window.HUACAPP_DATA || {};
  const baseAnimales = data.animales || [];
  let disponibles = [...baseAnimales];
  let ventas = data.ventas || [];
  let seleccionados = new Set();
  const POR_PAGINA = 6;
  let paginaActual = 1;
  let modal;
  let modalComprador;
  let chartInstance;
  let chartLabels = [];
  let chartSeries = [];
  const $ = (id) => document.getElementById(id);
  const dinero = (valor) => `$ ${Number(valor || 0).toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  const categoria = (a) => a.categoria || '-';
  const fechaHoy = () => new Date().toISOString().slice(0, 10);
  const csrf = () => document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.split('=')[1] || '';
  const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#039;'}[c]));

  function mostrar(texto, tipo) {
    const contenedor = $('mensaje-venta');
    if (!contenedor) return;
    contenedor.innerHTML = `<div class="alert alert-${tipo}">${escapeHtml(texto)}</div>`;
  }

  function actualizarTotales() {
    const pesoSeleccionado = disponibles.filter(a => seleccionados.has(a.id)).reduce((s, a) => s + Number(a.peso_actual_valor || 0), 0);
    const pesoManual = $('venta-peso-manual').checked;
    const pesoInput = $('venta-peso-total');
    const pesoDesbastadoInput = $('venta-peso-desbastado');
    const montoInput = $('venta-monto-total');
    const precio = Number($('venta-precio').value || 0);
    const desbaste = Math.min(100, Math.max(0, Number($('venta-desbaste').value || 0)));

    if (pesoManual) {
      pesoInput.removeAttribute('readonly');
    } else {
      pesoInput.setAttribute('readonly', 'readonly');
      pesoInput.value = pesoSeleccionado.toFixed(2);
    }

    const pesoFinal = pesoManual ? Number(pesoInput.value || 0) : pesoSeleccionado;
    const pesoDesbastado = pesoFinal * (1 - desbaste / 100);
    pesoDesbastadoInput.value = pesoDesbastado.toFixed(2);
    montoInput.value = dinero(pesoDesbastado * precio);
  }

  function obtenerFiltrados() {
    const especie = $('filtro-especie').value;
    const cat = $('filtro-categoria').value;
    const buscar = $('filtro-animal').value.toLowerCase();
    return disponibles.filter(a => (!especie || a.tipo_animal === especie) && (!cat || categoria(a) === cat) && (!buscar || `${a.caravana} ${a.nombre}`.toLowerCase().includes(buscar)));
  }

  function renderPaginacion(total) {
    const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));
    if (paginaActual > totalPaginas) paginaActual = totalPaginas;
    const info = $('paginacion-info');
    const actual = $('paginacion-actual');
    const prev = $('pagina-anterior');
    const next = $('pagina-siguiente');
    if (info) info.textContent = `${total} animal(es)`;
    if (actual) actual.textContent = `${paginaActual} / ${totalPaginas}`;
    if (prev) prev.disabled = paginaActual <= 1;
    if (next) next.disabled = paginaActual >= totalPaginas;
  }

  function renderAnimales() {
    const filtrados = obtenerFiltrados();
    renderPaginacion(filtrados.length);
    const inicio = (paginaActual - 1) * POR_PAGINA;
    const filas = filtrados.slice(inicio, inicio + POR_PAGINA).map(a => `
      <tr>
        <td><input class="form-check-input seleccionar-animal" type="checkbox" value="${a.id}" ${seleccionados.has(a.id) ? 'checked' : ''}></td>
        <td>${escapeHtml(a.caravana)}</td>
        <td>${escapeHtml(a.nombre)}</td>
        <td>${escapeHtml(a.tipo_animal)}</td>
        <td>${escapeHtml(categoria(a))}</td>
        <td class="text-end">${Number(a.peso_actual_valor || 0).toFixed(2)} kg</td>
      </tr>`).join('');

    $('animales-venta-body').innerHTML = filas || '<tr><td colspan="6" class="text-center text-secondary">No hay animales disponibles con ese filtro.</td></tr>';
    document.querySelectorAll('.seleccionar-animal').forEach(el => el.addEventListener('change', () => {
      const id = Number(el.value);
      if (el.checked) seleccionados.add(id);
      else seleccionados.delete(id);
      actualizarTotales();
    }));
  }

  function renderVentas() {
    $('ventas-body').innerHTML = ventas.map(v => `
      <tr>
        <td>${escapeHtml(v.fecha)}</td>
        <td>${escapeHtml(v.comprador)}</td>
        <td>${escapeHtml((v.animales || []).map(a => `#${a.caravana} ${a.nombre}`).join(', '))}</td>
        <td>${escapeHtml(v.establecimiento || '—')}</td>
        <td>${escapeHtml(v.peso_total)} kg</td>
        <td>${escapeHtml(v.peso_desbastado)} kg</td>
        <td>${dinero(v.precio_por_kg)}</td>
        <td class="text-end">${dinero(v.monto_total)}</td>
        <td><span class="badge ${v.estado_de_cobro === 'Pagada' ? 'text-bg-success' : 'text-bg-warning'}">${escapeHtml(v.estado_de_cobro)}</span></td>
        <td>${escapeHtml(v.metodo_de_pago)}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary editar" data-id="${v.id}" title="Editar"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger eliminar" data-id="${v.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="11" class="text-center text-secondary py-4">Todavía no hay ventas registradas.</td></tr>';

    document.querySelectorAll('.editar').forEach(b => b.onclick = () => abrirEdicion(Number(b.dataset.id)));
    document.querySelectorAll('.eliminar').forEach(b => b.onclick = () => eliminarVenta(Number(b.dataset.id)));
  }

  function renderResumenAnio() {
    const anioActual = String(new Date().getFullYear());
    const delAnio = ventas.filter(v => String(v.fecha || '').slice(0, 4) === anioActual);
    const ingresos = delAnio.reduce((s, v) => s + Number(v.monto_total || 0), 0);
    const kilos = delAnio.reduce((s, v) => s + Number(v.peso_desbastado || 0), 0);
    const el = (id) => document.getElementById(id);
    if (el('resumen-anio-cantidad')) el('resumen-anio-cantidad').textContent = delAnio.length;
    if (el('resumen-anio-ingresos')) el('resumen-anio-ingresos').textContent = dinero(ingresos);
    if (el('resumen-anio-kilos')) el('resumen-anio-kilos').textContent = `${kilos.toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2})} kg`;
  }

  function renderCompradores() {
    const tbody = $('compradores-body');
    if (!tbody) return;
    tbody.innerHTML = (data.compradores || []).map(c => `
      <tr>
        <td>${escapeHtml(c.nombre)}</td>
        <td>${escapeHtml(c.correo || c.dni || '-')}</td>
        <td>${escapeHtml(c.telefono || '-')}</td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-primary editar-comprador" data-id="${c.id}"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger eliminar-comprador" data-id="${c.id}"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('') || '<tr><td colspan="4" class="text-center text-secondary py-3">No hay compradores cargados.</td></tr>';

    document.querySelectorAll('.editar-comprador').forEach(btn => btn.onclick = () => abrirEdicionComprador(Number(btn.dataset.id)));
    document.querySelectorAll('.eliminar-comprador').forEach(btn => btn.onclick = () => eliminarComprador(Number(btn.dataset.id)));
  }

  function renderSummary() {
    const total = ventas.length;
    const ingresos = ventas.reduce((s, v) => s + Number(v.monto_total || 0), 0);
    const anioActual = String(new Date().getFullYear());
    const ingresosAnio = ventas.filter(v => String(v.fecha || '').slice(0, 4) === anioActual).reduce((s, v) => s + Number(v.monto_total || 0), 0);
    const mesesConVentas = new Set(ventas.map(v => String(v.fecha || '').slice(0, 7)));
    const promedio = mesesConVentas.size ? ingresos / mesesConVentas.size : 0;
    $('kpi-total-ventas').textContent = total;
    $('kpi-promedio-mes').textContent = dinero(promedio);
    $('kpi-ingresos-anio').textContent = dinero(ingresosAnio);
    $('kpi-compradores').textContent = (data.compradores || []).length;
  }

  function renderChart() {
    const chartEl = $('chart-ventas');
    if (!chartEl) return;
    const anioActual = new Date().getFullYear();
    chartLabels = [];
    for (let i = 4; i >= 0; i--) chartLabels.push(String(anioActual - i));
    chartSeries = chartLabels.map(anio => ventas.filter(v => String(v.fecha || '').slice(0, 4) === anio).reduce((s, v) => s + Number(v.monto_total || 0), 0));
    chartInstance?.destroy();
    chartInstance = new ApexCharts(chartEl, {
      chart: { type: 'bar', height: 320, toolbar: { show: false } },
      series: [{ name: 'Ingresos', data: chartSeries }],
      xaxis: { categories: chartLabels },
      colors: ['#198754'],
      dataLabels: { enabled: false },
      tooltip: { y: { formatter: value => dinero(value) } },
    });
    chartInstance.render();
  }

  function cargarSelectCompradores() {
    const select = $('venta-comprador');
    if (!select) return;
    const anterior = select.value;
    select.innerHTML = '<option value="">Sin comprador</option>';
    (data.compradores || []).forEach(c => select.add(new Option(escapeHtml(c.nombre), c.id)));
    if (anterior && [...select.options].some(o => o.value === anterior)) select.value = anterior;
  }

  function abrirNueva() {
    $('form-venta').reset();
    $('venta-id').value = '';
    $('venta-fecha').value = fechaHoy();
    $('venta-peso-manual').checked = false;
    $('titulo-venta').textContent = 'Registrar venta';
    seleccionados = new Set();
    paginaActual = 1;
    actualizarTotales();
    cargarSelectCompradores();
    renderAnimales();
    modal.show();
  }

  function abrirEdicion(id) {
    const v = ventas.find(x => x.id === id);
    if (!v) return;
    $('venta-id').value = id;
    $('venta-fecha').value = v.fecha;
    $('venta-comprador').value = v.comprador_id || '';
    $('venta-precio').value = v.precio_por_kg;
    $('venta-detalle').value = v.detalle;
    $('venta-peso-manual').checked = true;
    $('venta-peso-total').value = v.peso_total;
    $('venta-desbaste').value = v.porcentaje_desbaste || 0;
    $('venta-estado').value = v.estado_de_cobro || 'Pendiente';
    $('venta-metodo').value = v.metodo_de_pago || 'Efectivo';
    $('titulo-venta').textContent = `Editar venta #${id}`;
    const ids = new Set(v.animales.map(a => a.id));
    seleccionados = ids;
    paginaActual = 1;
    actualizarTotales();
    cargarSelectCompradores();
    renderAnimales();
    modal.show();
  }

  function abrirEdicionComprador(id) {
    const comprador = (data.compradores || []).find(c => c.id === id);
    if (!comprador) return;
    $('comprador-id').value = comprador.id;
    $('titulo-comprador').textContent = 'Editar comprador';
    const form = $('form-comprador');
    form.elements.dni.value = comprador.dni || '';
    form.elements.nombre.value = comprador.nombre || '';
    form.elements.apellido.value = comprador.apellido || '';
    form.elements.correo_electronico.value = comprador.correo || '';
    form.elements.fecha_nacimiento.value = comprador.fecha_nacimiento || '';
    form.elements.telefono.value = comprador.telefono || '';
    modalComprador.show();
  }

  async function eliminarComprador(id) {
    if (!confirm('¿Eliminar este comprador?')) return;
    const r = await fetch(`/api/compradores/${id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    if (!r.ok) return mostrar('No se pudo eliminar el comprador.', 'danger');
    data.compradores = (data.compradores || []).filter(c => c.id !== id);
    renderCompradores();
    cargarSelectCompradores();
    renderSummary();
    mostrar('Comprador eliminado.', 'success');
  }

  async function eliminarVenta(id) {
    if (!confirm('¿Eliminar la venta y restaurar sus animales al stock?')) return;
    const r = await fetch(`/api/ventas/${id}/eliminar/`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    if (!r.ok) return mostrar('No se pudo eliminar la venta.', 'danger');
    const venta = ventas.find(v => v.id === id);
    if (venta) {
      ventas = ventas.filter(v => v.id !== id);
      (venta.animales || []).forEach(a => {
        if (!disponibles.some(d => d.id === a.id)) disponibles.push(a);
      });
    }
    renderVentas();
    renderSummary();
    renderChart();
    renderAnimales();
    renderResumenAnio();
    mostrar('Venta eliminada. Los animales volvieron al stock.', 'success');
  }

  function actualizarFiltroCategoria() {
    const especie = $('filtro-especie').value;
    const grupo = $('grupo-filtro-categoria');
    const select = $('filtro-categoria');
    const visible = especie === 'Bovino';
    if (grupo) grupo.classList.toggle('d-none', !visible);
    if (select) {
      select.disabled = !visible;
      if (!visible) select.value = '';
    }
    paginaActual = 1;
    renderAnimales();
  }

  function seleccionarVisibles() {
    const filtrados = obtenerFiltrados();
    const inicio = (paginaActual - 1) * POR_PAGINA;
    const visibles = filtrados.slice(inicio, inicio + POR_PAGINA).map(a => Number(a.id));
    const todosSeleccionados = visibles.length > 0 && visibles.every(id => seleccionados.has(id));
    if (todosSeleccionados) {
      visibles.forEach(id => seleccionados.delete(id));
    } else {
      visibles.forEach(id => seleccionados.add(id));
    }
    actualizarTotales();
    renderAnimales();
  }

  document.addEventListener('DOMContentLoaded', () => {
    modal = new bootstrap.Modal($('modalVenta'));
    modalComprador = new bootstrap.Modal($('modalComprador'));

    renderSummary();
    renderCompradores();
    renderChart();
    renderVentas();
    renderResumenAnio();
    renderAnimales();
    actualizarFiltroCategoria();
    cargarSelectCompradores();

    $('nueva-venta').onclick = abrirNueva;
    $('nuevo-comprador').onclick = () => {
      $('form-comprador').reset();
      $('comprador-id').value = '';
      $('titulo-comprador').textContent = 'Nuevo comprador';
      modalComprador.show();
    };
    $('seleccionar-filtrados').onclick = seleccionarVisibles;
    $('pagina-anterior').onclick = () => {
      if (paginaActual > 1) {
        paginaActual--;
        renderAnimales();
      }
    };
    $('pagina-siguiente').onclick = () => {
      const totalPaginas = Math.max(1, Math.ceil(obtenerFiltrados().length / POR_PAGINA));
      if (paginaActual < totalPaginas) {
        paginaActual++;
        renderAnimales();
      }
    };

    ['filtro-especie', 'filtro-categoria', 'filtro-animal'].forEach(id => $(id).addEventListener('input', actualizarFiltroCategoria));
    $('venta-precio').addEventListener('input', actualizarTotales);
    $('venta-peso-manual').addEventListener('change', actualizarTotales);
    $('venta-peso-total').addEventListener('input', actualizarTotales);
    $('venta-desbaste').addEventListener('input', actualizarTotales);

    $('form-venta').addEventListener('submit', async e => {
      e.preventDefault();
      if (!seleccionados.size) return alert('Seleccioná al menos un animal.');

      const form = new FormData(e.target);
      seleccionados.forEach(id => form.append('animales', id));
      const id = $('venta-id').value;
      const r = await fetch(id ? `/api/ventas/${id}/` : '/api/ventas/', { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form });
      const respuesta = await r.json();
      if (!r.ok) return alert(respuesta.error || 'No se pudo guardar la venta.');
      const ventaData = respuesta.venta;
      const esNueva = !id;

      if (esNueva) {
        ventas.unshift(ventaData);
      } else {
        const idx = ventas.findIndex(v => v.id === Number(id));
        if (idx !== -1) {
          ventas[idx].animales.forEach(a => {
            if (!disponibles.some(d => d.id === a.id)) disponibles.push(a);
          });
          ventas[idx] = ventaData;
        }
      }
      ventaData.animales.forEach(a => { disponibles = disponibles.filter(d => d.id !== a.id); });
      seleccionados = new Set();
      renderVentas();
      renderSummary();
      renderChart();
      renderAnimales();
      renderResumenAnio();
      modal.hide();
      mostrar('Venta guardada.', 'success');
    });

    $('form-comprador').addEventListener('submit', async e => {
      e.preventDefault();
      const form = new FormData(e.target);
      const dni = String(form.get('dni') || '').trim();
      if (dni && (dni.length < 7 || dni.length > 8)) {
        alert('El DNI debe tener entre 7 y 8 caracteres.');
        return;
      }
      const compradorId = $('comprador-id').value;
      const url = compradorId ? `/api/compradores/${compradorId}/` : '/api/compradores/';
      const r = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form });
      const respuesta = await r.json();
      if (!r.ok) return alert(respuesta.error || 'No se pudo guardar el comprador.');
      data.compradores = data.compradores || [];
      if (compradorId) {
        const idx = data.compradores.findIndex(c => c.id === Number(compradorId));
        if (idx !== -1) data.compradores[idx] = respuesta.comprador;
      } else {
        data.compradores.push(respuesta.comprador);
      }
      renderCompradores();
      cargarSelectCompradores();
      renderSummary();
      modalComprador.hide();
      mostrar('Comprador guardado.', 'success');
    });
  });
})();
