const SELECTOR_SIDEBAR_WRAPPER = '.sidebar-wrapper';
const Default = {
  scrollbarTheme: 'os-theme-light',
  scrollbarAutoHide: 'leave',
  scrollbarClickScroll: true,
};
document.addEventListener('DOMContentLoaded', function () {
  const sidebarWrapper = document.querySelector(SELECTOR_SIDEBAR_WRAPPER);
  const isMobile = window.innerWidth <= 992;
  if (
    sidebarWrapper &&
    OverlayScrollbarsGlobal?.OverlayScrollbars !== undefined &&
    !isMobile
  ) {
    OverlayScrollbarsGlobal.OverlayScrollbars(sidebarWrapper, {
      scrollbars: {
        theme: Default.scrollbarTheme,
        autoHide: Default.scrollbarAutoHide,
        clickScroll: Default.scrollbarClickScroll,
      },
    });
  }
});

(() => {
  'use strict';
  const STORAGE_KEY = 'lte-theme';
  const getStoredTheme = () => localStorage.getItem(STORAGE_KEY);
  const setStoredTheme = (theme) => localStorage.setItem(STORAGE_KEY, theme);
  const prefersDark = () => globalThis.matchMedia('(prefers-color-scheme: dark)').matches;
  const getPreferredTheme = () => {
    const stored = getStoredTheme();
    if (stored) return stored;
    return prefersDark() ? 'dark' : 'light';
  };
  const setTheme = (theme) => {
    const resolved = theme === 'auto' ? (prefersDark() ? 'dark' : 'light') : theme;
    document.documentElement.setAttribute('data-bs-theme', resolved);
  };
  setTheme(getPreferredTheme());
  const showActiveTheme = (theme) => {
    document.querySelectorAll('[data-bs-theme-value]').forEach((el) => {
      el.classList.remove('active');
      el.setAttribute('aria-pressed', 'false');
      const check = el.querySelector('.bi-check-lg');
      if (check) check.classList.add('d-none');
    });
    const active = document.querySelector(`[data-bs-theme-value="${theme}"]`);
    if (active) {
      active.classList.add('active');
      active.setAttribute('aria-pressed', 'true');
      const check = active.querySelector('.bi-check-lg');
      if (check) check.classList.remove('d-none');
    }
    document.querySelectorAll('[data-lte-theme-icon]').forEach((icon) => {
      icon.classList.toggle('d-none', icon.dataset.lteThemeIcon !== theme);
    });
  };
  globalThis.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const stored = getStoredTheme();
    if (!stored || stored === 'auto') setTheme(getPreferredTheme());
  });
  document.addEventListener('DOMContentLoaded', () => {
    showActiveTheme(getPreferredTheme());
    document.querySelectorAll('[data-bs-theme-value]').forEach((toggle) => {
      toggle.addEventListener('click', () => {
        const theme = toggle.getAttribute('data-bs-theme-value');
        setStoredTheme(theme);
        setTheme(theme);
        showActiveTheme(theme);
      });
    });
  });
})();

// ------------------------------------------------------------------
// DATOS: provienen del servidor (Django) filtrados por establecimiento
// ------------------------------------------------------------------
const GANASTOCK = window.GANASTOCK_DATA || {};
const KPIS = GANASTOCK.kpis ?? {
  total_animales: 0,
  ventas_mes: 0,
  gastos_mes: 0,
  peso_promedio: 0,
  ingresos_mes: 0,
};

const formatoMoneda = (valor) => {
  const numero = Number(valor || 0);
  return `$${numero.toLocaleString('es-AR', { maximumFractionDigits: 0 })}`;
};

function renderKPIs() {
  const totalAnimales = document.getElementById('kpi-total-animales');
  const ventasMes = document.getElementById('kpi-ventas-mes');
  const gastosMes = document.getElementById('kpi-gastos-mes');
  const pesoPromedio = document.getElementById('kpi-peso-promedio');
  const ingresosMes = document.getElementById('kpi-ingresos-mes');
  if (totalAnimales) totalAnimales.textContent = Number(KPIS.total_animales || 0).toLocaleString('es-AR');
  if (ventasMes) ventasMes.textContent = Number(KPIS.ventas_mes || 0).toLocaleString('es-AR');
  if (gastosMes) gastosMes.textContent = formatoMoneda(KPIS.gastos_mes);
  if (pesoPromedio) pesoPromedio.textContent = `${Number(KPIS.peso_promedio || 0).toLocaleString('es-AR')} kg`;
  if (ingresosMes) ingresosMes.textContent = formatoMoneda(KPIS.ingresos_mes);
}

function renderReloj() {
  const ahora = new Date();
  const fecha = ahora.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const hora = ahora.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  document.getElementById('fecha-actual').textContent = fecha.charAt(0).toUpperCase() + fecha.slice(1);
  document.getElementById('hora-actual').textContent = hora;
}

const DISTRIBUCION = GANASTOCK.distribucion ?? {};

const COLORES_CATEGORIA = {
  Vaca: '#198754',
  Toro: '#0d6efd',
  Novillo: '#6c757d',
  Vaquillona: '#ffc107',
  Ternero: '#20c997',
  Bovino: '#0dcaf0',
  Porcino: '#fd7e14',
  Ovino: '#d63384',
};

function renderGraficos() {
  const chartGanancias = document.querySelector('#chart-ganancias-gastos');
  if (chartGanancias) {
    const labels = JSON.parse(GANASTOCK.chart?.labels_json ?? '[]');
    const ingresos = JSON.parse(GANASTOCK.chart?.ingresos_json ?? '[]');
    const egresos = JSON.parse(GANASTOCK.chart?.egresos_json ?? '[]');

    const series = labels.length
      ? [
          { name: 'Ganancias', data: ingresos },
          { name: 'Gastos', data: egresos },
        ]
      : [
          { name: 'Ganancias', data: [0] },
          { name: 'Gastos', data: [0] },
        ];

    new ApexCharts(chartGanancias, {
      series,
      chart: { height: 300, type: 'bar', toolbar: { show: false } },
      colors: ['#198754', '#dc3545'],
      plotOptions: { bar: { columnWidth: '55%', borderRadius: 4 } },
      dataLabels: { enabled: false },
      legend: { position: 'top' },
      xaxis: {
        categories: labels.length ? labels : [],
      },
      yaxis: {
        labels: { formatter: (val) => `$${Number(val).toLocaleString('es-AR', { maximumFractionDigits: 0 })}` },
      },
    }).render();
  }

  // Distribucion del rodeo (por categoria de animal)
  const chartDistribucion = document.querySelector('#chart-distribucion');
  if (chartDistribucion) {
    const categorias = Object.keys(DISTRIBUCION);
    const series = categorias.length ? categorias.map((categoria) => DISTRIBUCION[categoria]) : [0];
    const labels = categorias.length ? categorias : ['Sin datos'];
    const colors = categorias.length ? categorias.map((categoria) => COLORES_CATEGORIA[categoria] || '#6c757d') : ['#dee2e6'];

    new ApexCharts(chartDistribucion, {
      series,
      chart: { height: 300, type: 'donut' },
      labels,
      colors,
      legend: { position: 'bottom' },
    }).render();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  renderReloj();
  setInterval(renderReloj, 30000);
  renderKPIs();
  renderGraficos();

  document.getElementById('btn-actualizar').addEventListener('click', function () {
    const icon = this.querySelector('i');
    icon.classList.add('spin');
    renderReloj();
    setTimeout(() => icon.classList.remove('spin'), 500);
  });
});
