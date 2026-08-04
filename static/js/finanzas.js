function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

document.addEventListener('DOMContentLoaded', function () {
  // Render chart
  try {
    new ApexCharts(document.querySelector('#chart-finanzas'), {
      chart: { height: 320, type: 'bar', toolbar: { show: false } },
      series: [
        { name: 'Ingresos', data: CHART_INGRESOS },
        { name: 'Egresos', data: CHART_EGRESOS },
      ],
      xaxis: { categories: CHART_LABELS },
      colors: ['#198754', '#dc3545'],
      dataLabels: { enabled: false },
      stroke: { show: true, width: 2, colors: ['transparent'] },
    }).render();
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
        // refrescar para ver nuevo movimiento y KPIs
        window.location.reload();
      }).catch(err => {
        console.error(err);
        alert('Error al crear movimiento.');
      });
    });
  }

  // Eliminar
  document.querySelectorAll('.btn-eliminar').forEach(btn => {
    btn.addEventListener('click', function () {
      const id = this.dataset.id;
      if (!confirm('Confirma eliminar este movimiento financiero?')) return;
      fetch(`/api/finanzas/movimientos/${id}/eliminar/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      }).then(res => res.json()).then(data => {
        if (data.ok) {
          document.querySelector(`tr[data-id="${id}"]`).remove();
        } else {
          alert('No se pudo eliminar.');
        }
      }).catch(err => {
        console.error(err);
        alert('Error al eliminar movimiento.');
      });
    });
  });
});
