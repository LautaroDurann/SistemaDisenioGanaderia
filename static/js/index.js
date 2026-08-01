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
// MOCK DATA: reemplazar por datos reales cuando se conecte con Django
// ------------------------------------------------------------------
const ULTIMOS_MOVIMIENTOS = window.GANASTOCK_DATA?.movimientos ?? [
  { fecha: '14/07/2026', animal: '#0231 Luna', tipo: 'Ingreso', usuario: 'Juan', obs: 'Compra a La Esperanza' },
  { fecha: '13/07/2026', animal: '#0198 Fierro', tipo: 'Venta', usuario: 'Carlos', obs: 'Remate feria local' },
  { fecha: '12/07/2026', animal: '#0305 S/N', tipo: 'Nacimiento', usuario: 'Maria', obs: 'Nacimiento en Potrero 2' },
  { fecha: '10/07/2026', animal: '#0142 Estrella', tipo: 'Muerte', usuario: 'Carlos', obs: 'Causas naturales' },
  { fecha: '10/07/2026', animal: '#0087 S/N', tipo: 'Traslado', usuario: 'Maria', obs: 'Traslado por pastura' },
  { fecha: '09/07/2026', animal: '#0056 Paloma', tipo: 'Compra', usuario: 'Juan', obs: 'Reposicion de rodeo' },
  { fecha: '08/07/2026', animal: '#0412 S/N', tipo: 'Alta', usuario: 'Maria', obs: 'Alta por nacimiento tardio' },
  { fecha: '06/07/2026', animal: '#0329 S/N', tipo: 'Baja', usuario: 'Carlos', obs: 'Baja administrativa' },
  { fecha: '05/07/2026', animal: '#0263 Rocio', tipo: 'Traslado', usuario: 'Juan', obs: 'Rotacion de pastoreo' },
  { fecha: '03/07/2026', animal: '#0177 Trueno', tipo: 'Ingreso', usuario: 'Maria', obs: 'Ingreso por servicio' },
];

const TIPO_BADGE = {
  Ingreso: 'text-bg-success',
  Venta: 'text-bg-danger',
  Muerte: 'text-bg-warning',
  Traslado: 'text-bg-primary',
  Nacimiento: 'text-bg-info',
  Compra: 'text-bg-warning',
  Baja: 'text-bg-dark',
  Alta: 'text-bg-success',
};

function renderReloj() {
  const ahora = new Date();
  const fecha = ahora.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const hora = ahora.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  document.getElementById('fecha-actual').textContent = fecha.charAt(0).toUpperCase() + fecha.slice(1);
  document.getElementById('hora-actual').textContent = hora;
}

function renderTablaMovimientos() {
  document.getElementById('tabla-ultimos-mov').innerHTML = ULTIMOS_MOVIMIENTOS.slice(0, 10)
    .map(
      (m) => `
    <tr>
      <td>${m.fecha}</td>
      <td>${m.animal}</td>
      <td><span class="badge ${TIPO_BADGE[m.tipo] || 'text-bg-secondary'}">${m.tipo}</span></td>
      <td>${m.usuario}</td>
      <td>${m.obs}</td>
    </tr>`,
    )
    .join('');
}

function renderGraficos() {
  // Ganancias vs Gastos - 12 meses
  new ApexCharts(document.querySelector('#chart-ganancias-gastos'), {
    series: [
      { name: 'Ganancias', data: [3200, 3450, 3100, 3800, 4200, 3950, 4500, 4600, 4750, 5000, 5200, 5600] },
      { name: 'Gastos', data: [2100, 2200, 2150, 2400, 2600, 2500, 2700, 2650, 2750, 2800, 2800, 2900] },
    ],
    chart: { height: 300, type: 'bar', toolbar: { show: false } },
    colors: ['#198754', '#dc3545'],
    plotOptions: { bar: { columnWidth: '55%', borderRadius: 4 } },
    dataLabels: { enabled: false },
    legend: { position: 'top' },
    xaxis: {
      categories: ['Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul'],
    },
    yaxis: {
      labels: { formatter: (val) => `$${val.toLocaleString('es-AR')}` },
    },
  }).render();

  // Distribucion del rodeo (por categoria de animal)
  new ApexCharts(document.querySelector('#chart-distribucion'), {
    series: [96, 18, 42, 30, 74],
    chart: { height: 300, type: 'donut' },
    labels: ['Vacas', 'Toros', 'Novillos', 'Vaquillonas', 'Terneros'],
    colors: ['#198754', '#0d6efd', '#6c757d', '#ffc107', '#20c997'],
    legend: { position: 'bottom' },
  }).render();
}

document.addEventListener('DOMContentLoaded', () => {
  renderReloj();
  setInterval(renderReloj, 30000);
  renderTablaMovimientos();
  renderGraficos();

  document.getElementById('btn-actualizar').addEventListener('click', function () {
    const icon = this.querySelector('i');
    icon.classList.add('spin');
    renderReloj();
    setTimeout(() => icon.classList.remove('spin'), 500);
  });
});
