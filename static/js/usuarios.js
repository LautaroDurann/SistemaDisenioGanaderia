const SELECTOR_SIDEBAR_WRAPPER = '.sidebar-wrapper';
const Default = {
  scrollbarTheme: 'os-theme-light',
  scrollbarAutoHide: 'leave',
  scrollbarClickScroll: true,
};
document.addEventListener('DOMContentLoaded', function () {
  const sidebarWrapper = document.querySelector(SELECTOR_SIDEBAR_WRAPPER);
  const isMobile = window.innerWidth <= 992;
  if (sidebarWrapper && OverlayScrollbarsGlobal?.OverlayScrollbars !== undefined && !isMobile) {
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
// Usuarios: datos reales servidos por Django.
// ------------------------------------------------------------------
const COLOR_ROL = {
  'Propietario': '#1d4e43',
  'Operario': '#6c757d',
};

const ESTADO_BADGE = {
  Activo: 'text-bg-success',
  Inactivo: 'text-bg-secondary',
};

let USUARIOS = window.HUACAPP_DATA?.usuarios ?? [];
const ESTABLECIMIENTOS = window.HUACAPP_DATA?.establecimientos ?? [];
const USUARIO_ACTUAL_ID = window.HUACAPP_DATA?.usuario_actual_id ?? null;

const FILAS_POR_PAGINA = 6;
let paginaActual = 1;
let usuarioSeleccionado = null;
let usuarioEdicion = null;

function nombreCompleto(u) {
  return `${u.nombre || ''} ${u.apellido || ''}`.trim();
}

function iniciales(u) {
  const n = (u.nombre || '?')[0] || '?';
  const a = (u.apellido || ' ')[0] || '';
  return `${n}${a}`.toUpperCase();
}

function formatFecha(iso) {
  if (!iso) return '-';
  const [fecha] = String(iso).split('T');
  const [y, m, d] = fecha.split('-');
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}

function formatFechaHora(iso) {
  if (!iso) return '-';
  const [fecha, hora] = String(iso).split('T');
  const limpia = hora ? hora.split('.')[0].replace(/[+Z].*$/, '').slice(0, 5) : '';
  return `${formatFecha(fecha)}${limpia ? ` ${limpia}` : ''}`;
}

function getCookie(nombre) {
  const valor = `; ${document.cookie}`;
  const partes = valor.split(`; ${nombre}=`);
  if (partes.length === 2) return partes.pop().split(';').shift();
  return '';
}

function apiFetch(url, datos) {
  const body = new URLSearchParams();
  Object.entries(datos || {}).forEach(([clave, valor]) => {
    if (Array.isArray(valor)) {
      valor.forEach((item) => body.append(clave, item));
    } else {
      body.append(clave, valor);
    }
  });
  return fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCookie('csrftoken') },
    body,
  }).then(async (respuesta) => {
    const cuerpo = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) throw new Error(cuerpo.error || 'No se pudo completar la acción.');
    return cuerpo;
  });
}

function aplicarFiltros() {
  const buscar = document.getElementById('f-buscar').value.trim().toLowerCase();
  const rol = document.getElementById('f-rol').value;
  const estado = document.getElementById('f-estado').value;

  return USUARIOS.filter((u) => {
    if (buscar && !`${nombreCompleto(u)} ${u.email} ${u.usuario}`.toLowerCase().includes(buscar)) return false;
    if (rol && !(u.roles || []).some((r) => r.rol === rol) && u.rol !== rol) return false;
    if (estado && u.estado !== estado) return false;
    return true;
  });
}

function badgesRoles(u) {
  if (u.rol === 'Propietario') {
    return '<span class="badge text-bg-light border me-1" title="Accede a todos los establecimientos">Propietario</span>';
  }
  const roles = u.roles || [];
  if (!roles.length) return u.rol || '-';
  return roles
    .map(
      (r) =>
        `<span class="badge text-bg-light border me-1" title="${r.establecimiento_nombre} · ${r.estado}">${r.rol}</span>`,
    )
    .join('');
}

function avatarHtml(u) {
  if (u.foto_url) {
    return `<span class="vacapp-avatar-wrap">
      <span class="vacapp-avatar" style="background:#fff; overflow:hidden;">
        <img src="${u.foto_url}" alt="Foto de ${nombreCompleto(u) || 'usuario'}" class="w-100 h-100" style="object-fit:cover;">
      </span>
      ${u.conectado ? '<span class="vacapp-online-dot" title="Conectado ahora"></span>' : ''}
    </span>`;
  }
  return `<span class="vacapp-avatar-wrap">
    <span class="vacapp-avatar" style="background:${COLOR_ROL[u.rol] || '#6c757d'}">${iniciales(u)}</span>
    ${u.conectado ? '<span class="vacapp-online-dot" title="Conectado ahora"></span>' : ''}
  </span>`;
}

function renderTabla() {
  const filtrados = aplicarFiltros();
  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / FILAS_POR_PAGINA));
  if (paginaActual > totalPaginas) paginaActual = totalPaginas;
  const inicio = (paginaActual - 1) * FILAS_POR_PAGINA;
  const pagina = filtrados.slice(inicio, inicio + FILAS_POR_PAGINA);

  document.getElementById('tabla-usuarios-body').innerHTML = pagina
    .map(
      (u) => `
    <tr>
      <td>
        ${avatarHtml(u)}
      </td>
      <td>
        <div class="fw-semibold">${nombreCompleto(u) || 'Sin nombre'}</div>
        <div class="small text-secondary">@${u.usuario}</div>
      </td>
      <td>${u.email || '-'}</td>
      <td>${badgesRoles(u)}</td>
      <td><span class="badge ${ESTADO_BADGE[u.estado] || 'text-bg-secondary'}">${u.estado}</span></td>
      <td>${formatFechaHora(u.acceso)}</td>
      <td>${formatFecha(u.creado)}</td>
      <td class="text-end">
        <button type="button" class="btn btn-sm btn-outline-primary btn-ver-perfil" data-id="${u.id}" title="Ver perfil">
          <i class="bi bi-eye"></i>
        </button>
        <div class="dropdown d-inline-block">
          <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
            <i class="bi bi-three-dots-vertical"></i>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li><a class="dropdown-item btn-editar-rol" href="#" data-id="${u.id}"><i class="bi bi-pencil-square me-2"></i>Editar información</a></li>
            <li><a class="dropdown-item btn-restablecer-clave" href="#" data-id="${u.id}"><i class="bi bi-key me-2"></i>Restablecer contraseña</a></li>
            <li><a class="dropdown-item btn-cambiar-estado" href="#" data-id="${u.id}"><i class="bi bi-slash-circle me-2"></i>${u.estado === 'Activo' ? 'Desactivar' : 'Activar'}</a></li>
            <li><hr class="dropdown-divider" /></li>
            <li><a class="dropdown-item text-danger btn-eliminar-usuario" href="#" data-id="${u.id}"><i class="bi bi-trash me-2"></i>Eliminar</a></li>
          </ul>
        </div>
      </td>
    </tr>`,
    )
    .join('');

  document.getElementById('tabla-resumen').textContent =
    filtrados.length === 0
      ? 'Sin resultados para los filtros aplicados.'
      : `Mostrando ${inicio + 1}-${Math.min(inicio + FILAS_POR_PAGINA, filtrados.length)} de ${filtrados.length} usuarios.`;

  const paginacion = document.getElementById('tabla-paginacion');
  paginacion.innerHTML = '';
  for (let i = 1; i <= totalPaginas; i++) {
    const li = document.createElement('li');
    li.className = `page-item ${i === paginaActual ? 'active' : ''}`;
    li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
    li.addEventListener('click', (e) => {
      e.preventDefault();
      paginaActual = i;
      renderTabla();
    });
    paginacion.appendChild(li);
  }

  document.querySelectorAll('.btn-ver-perfil').forEach((btn) => {
    btn.addEventListener('click', () => {
      usuarioSeleccionado = Number(btn.dataset.id);
      renderPerfil();
      document.getElementById('perfil-usuario').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  document.querySelectorAll('.btn-editar-rol').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      abrirModalRol(Number(btn.dataset.id));
    });
  });

  document.querySelectorAll('.btn-restablecer-clave').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const clave = prompt('Ingresá la nueva contraseña (mínimo 6 caracteres):');
      if (!clave) return;
      if (clave.length < 6) {
        alert('La contraseña debe tener al menos 6 caracteres.');
        return;
      }
      try {
        await apiFetch(`/api/usuarios/${btn.dataset.id}/`, { clave });
        alert('Contraseña actualizada.');
      } catch (error) {
        alert(error.message);
      }
    });
  });

  document.querySelectorAll('.btn-cambiar-estado').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const u = USUARIOS.find((x) => x.id === Number(btn.dataset.id));
      const nuevoEstado = u && u.estado === 'Activo' ? 'Inactivo' : 'Activo';
      try {
        await apiFetch(`/api/usuarios/${btn.dataset.id}/`, { estado_acceso: nuevoEstado });
        await cargarUsuarios();
      } catch (error) {
        alert(error.message);
      }
    });
  });

  document.querySelectorAll('.btn-eliminar-usuario').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const u = USUARIOS.find((x) => x.id === Number(btn.dataset.id));
      if (!u) return;
      if (!confirm(`¿Dar de baja al usuario ${nombreCompleto(u) || u.usuario}? Perderá el acceso al sistema.`)) return;
      try {
        await apiFetch(`/api/usuarios/${btn.dataset.id}/eliminar/`, {});
        await cargarUsuarios();
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

function sincronizarNavbarCon(u) {
  if (!u || USUARIO_ACTUAL_ID == null || u.id !== Number(USUARIO_ACTUAL_ID)) return;
  const color = COLOR_ROL[u.rol] || '#6c757d';
  const texto = iniciales(u);
  const src = u.foto_url
    ? `${u.foto_url}${u.foto_url.includes('?') ? '&' : '?'}t=${Date.now()}`
    : '';
  const armarSpan = (grande) => {
    const span = document.createElement('span');
    span.className = `vacapp-navbar-iniciales rounded-circle shadow${grande ? ' vacapp-navbar-iniciales-lg d-flex align-items-center justify-content-center' : ''}`;
    span.style.background = color;
    span.title = 'User Image';
    span.textContent = texto;
    return span;
  };
  const sincronizar = (contenedor, claseImg, grande) => {
    if (!contenedor) return;
    const span = contenedor.querySelector('.vacapp-navbar-iniciales');
    const img = contenedor.querySelector(`img.${claseImg}`);
    if (src) {
      if (span) span.remove();
      if (!img) {
        const nuevo = document.createElement('img');
        nuevo.className = `${claseImg} shadow`;
        nuevo.alt = 'User Image';
        nuevo.src = src;
        contenedor.insertBefore(nuevo, contenedor.firstChild);
      } else {
        img.src = src;
      }
    } else {
      if (span) {
        span.style.background = color;
        span.textContent = texto;
      } else if (img) {
        img.replaceWith(armarSpan(grande));
      }
    }
  };
  sincronizar(document.querySelector('.user-menu .nav-link'), 'user-image', false);
  sincronizar(document.querySelector('.user-menu .user-header'), 'rounded-circle', true);
}

function renderPerfil() {
  const u = USUARIOS.find((x) => x.id === usuarioSeleccionado) || USUARIOS[0];
  if (!u) {
    document.getElementById('perfil-nombre').textContent = 'Sin usuarios';
    document.getElementById('perfil-cargo').textContent = '-';
    document.getElementById('perfil-email').textContent = '-';
    document.getElementById('perfil-telefono').textContent = '-';
    document.getElementById('perfil-rol').textContent = '-';
    document.getElementById('perfil-establecimientos').textContent = '-';
    document.getElementById('perfil-estado').textContent = '-';
    document.getElementById('perfil-creacion').textContent = '-';
    document.getElementById('perfil-acceso').textContent = '-';
    return;
  }

  const avatar = document.getElementById('perfil-avatar');
  if (u.foto_url) {
    avatar.style.background = '#fff';
    avatar.innerHTML = `<img src="${u.foto_url}" alt="Foto de ${nombreCompleto(u) || 'usuario'}" class="w-100 h-100 rounded-circle" style="object-fit:cover;">`;
  } else {
    avatar.textContent = iniciales(u);
    avatar.style.background = COLOR_ROL[u.rol] || '#6c757d';
  }
  document.getElementById('btn-eliminar-foto').classList.toggle('d-none', !u.foto_url);

  document.getElementById('perfil-nombre').textContent = nombreCompleto(u) || u.usuario;
  document.getElementById('perfil-cargo').textContent = u.rol;
  document.getElementById('perfil-email').textContent = u.email || '-';
  document.getElementById('perfil-telefono').textContent = u.telefono || '-';
  document.getElementById('perfil-rol').textContent = u.rol;
  document.getElementById('perfil-establecimientos').textContent =
    u.rol === 'Propietario'
      ? 'Todos los establecimientos'
      : (u.roles || []).map((r) => r.establecimiento_nombre).join(', ') || '-';
  document.getElementById('perfil-estado').innerHTML = `<span class="badge ${ESTADO_BADGE[u.estado] || 'text-bg-secondary'}">${u.estado}</span>`;
  document.getElementById('perfil-creacion').textContent = formatFecha(u.creado);
  document.getElementById('perfil-acceso').textContent = formatFechaHora(u.acceso);
}

function crearCheckEstablecimiento(e, marcado) {
  const div = document.createElement('div');
  div.className = 'form-check';
  div.innerHTML = `
    <input class="form-check-input est-check" type="checkbox" id="est-${e.id}" value="${e.id}"${marcado ? ' checked' : ''}>
    <label class="form-check-label" for="est-${e.id}">${e.nombre}</label>`;
  return div;
}

function llenarChecksEstablecimientos(contenedor, marcados) {
  contenedor.innerHTML = '';
  ESTABLECIMIENTOS.forEach((e) =>
    contenedor.appendChild(crearCheckEstablecimiento(e, marcados && marcados.has(e.id))),
  );
}

function aplicarRolModal(rol, esNuevo, estado) {
  const esProp = rol === 'Propietario';
  const esInactivo = estado === 'Inactivo';
  const nota = document.getElementById(esNuevo ? 'nu-rol-note' : 'ar-rol-note');
  const cont = document.getElementById(esNuevo ? 'nu-est-container' : 'ar-est-container');
  if (nota) nota.classList.toggle('d-none', !esProp);
  // La lista de establecimientos se oculta para propietarios y usuarios inactivos.
  if (cont) cont.style.display = esProp || esInactivo ? 'none' : '';
}

function abrirModalRol(usuarioId) {
  const u = USUARIOS.find((x) => x.id === usuarioId);
  if (!u) return;
  usuarioEdicion = usuarioId;
  document.getElementById('ar-usuario-nombre').textContent = `Editando a ${nombreCompleto(u) || u.usuario} (@${u.usuario})`;
  document.getElementById('ar-nombre').value = u.nombre || '';
  document.getElementById('ar-apellido').value = u.apellido || '';
  document.getElementById('ar-email').value = u.email || '';
  document.getElementById('ar-telefono').value = u.telefono || '';
  document.getElementById('ar-rol-user').value = u.rol;
  document.getElementById('ar-estado-user').value = u.estado;
  const marcados = new Set((u.roles || []).map((r) => r.establecimiento_id));
  llenarChecksEstablecimientos(document.getElementById('ar-establecimientos'), marcados);
  aplicarRolModal(u.rol, false, u.estado);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('modalAsignarRol')).show();
}

async function cargarUsuarios() {
  try {
    const respuesta = await fetch('/api/usuarios/', { method: 'GET' });
    const cuerpo = await respuesta.json();
    USUARIOS = cuerpo.usuarios ?? [];
    if (usuarioSeleccionado && !USUARIOS.some((u) => u.id === usuarioSeleccionado)) {
      usuarioSeleccionado = null;
    }
    renderTabla();
    renderPerfil();
  } catch {
    renderTabla();
    renderPerfil();
  }
}

function ajustarAlturaFilaCompleta() {
  const fila = document.getElementById('perfil-usuario');
  if (!fila) return;
  const footer = document.querySelector('.app-footer');
  const top = fila.getBoundingClientRect().top;
  const footerHeight = footer ? footer.getBoundingClientRect().height : 0;
  const margenInferior = 24;
  const disponible = window.innerHeight - top - footerHeight - margenInferior;
  fila.style.minHeight = Math.max(disponible, 420) + 'px';
}

document.addEventListener('DOMContentLoaded', () => {
  if (!ESTABLECIMIENTOS.length) {
    fetch('/api/establecimientos/', { method: 'GET' })
      .then((respuesta) => respuesta.json())
      .then((data) => ESTABLECIMIENTOS.push(...(data.establecimientos || [])))
      .catch(() => {});
  }
  if (!USUARIOS.length) {
    cargarUsuarios();
  }

  renderTabla();
  renderPerfil();
  ajustarAlturaFilaCompleta();

  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(ajustarAlturaFilaCompleta, 150);
  });

  ['f-buscar', 'f-rol', 'f-estado'].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
      paginaActual = 1;
      renderTabla();
    });
  });

  document.getElementById('btn-limpiar-filtros').addEventListener('click', () => {
    document.getElementById('f-buscar').value = '';
    document.getElementById('f-rol').value = '';
    document.getElementById('f-estado').value = '';
    paginaActual = 1;
    renderTabla();
  });

  // Alta de usuario
  const form = document.getElementById('form-nuevo-usuario');
  const pass = document.getElementById('nu-password');
  const passConfirm = document.getElementById('nu-password-confirm');

  passConfirm.addEventListener('input', () => passConfirm.classList.remove('is-invalid'));

  llenarChecksEstablecimientos(document.getElementById('nu-establecimientos'), new Set());
  document.getElementById('nu-rol').addEventListener('change', (e) => {
    aplicarRolModal(e.target.value, true);
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (pass.value !== passConfirm.value) {
      passConfirm.classList.add('is-invalid');
      return;
    }
    passConfirm.classList.remove('is-invalid');
    const rol = document.getElementById('nu-rol').value;
    const establecimiento_ids = [];
    if (rol === 'Operario') {
      document.querySelectorAll('#nu-establecimientos input:checked').forEach((cb) => {
        establecimiento_ids.push(cb.value);
      });
      if (!establecimiento_ids.length) {
        alert('Seleccioná al menos un establecimiento para el usuario.');
        return;
      }
    }
    const datos = {
      nombre: document.getElementById('nu-nombre').value,
      apellido: document.getElementById('nu-apellido').value,
      email: document.getElementById('nu-email').value,
      telefono: document.getElementById('nu-telefono').value,
      usuario: document.getElementById('nu-usuario').value,
      clave: pass.value,
      rol,
      establecimiento_ids,
    };
    try {
      await apiFetch('/api/usuarios/', datos);
      bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNuevoUsuario')).hide();
      form.reset();
      document.getElementById('nu-rol').value = 'Operario';
      llenarChecksEstablecimientos(document.getElementById('nu-establecimientos'), new Set());
      aplicarRolModal('Operario', true);
      await cargarUsuarios();
    } catch (error) {
      alert(error.message);
    }
  });

  // Cambio de rol / estado
  document.getElementById('ar-rol-user').addEventListener('change', (e) => {
    aplicarRolModal(e.target.value, false, document.getElementById('ar-estado-user').value);
  });

  document.getElementById('ar-estado-user').addEventListener('change', (e) => {
    aplicarRolModal(document.getElementById('ar-rol-user').value, false, e.target.value);
  });

  document.getElementById('btn-guardar-rol').addEventListener('click', async () => {
    if (!usuarioEdicion) return;
    const url = `/api/usuarios/${usuarioEdicion}/`;
    const rol = document.getElementById('ar-rol-user').value;
    const estado = document.getElementById('ar-estado-user').value;
    const nombre = document.getElementById('ar-nombre').value.trim();
    if (!nombre) {
      alert('El nombre es obligatorio.');
      return;
    }
    const establecimiento_ids = [];
    if (rol === 'Operario') {
      document.querySelectorAll('#ar-establecimientos input:checked').forEach((cb) => {
        establecimiento_ids.push(cb.value);
      });
      if (!establecimiento_ids.length) {
        alert('Seleccioná al menos un establecimiento para el usuario.');
        return;
      }
    }
    try {
      await apiFetch(url, {
        nombre,
        apellido: document.getElementById('ar-apellido').value,
        email: document.getElementById('ar-email').value,
        telefono: document.getElementById('ar-telefono').value,
        rol,
        estado_acceso: estado,
        establecimiento_ids,
      });
      bootstrap.Modal.getOrCreateInstance(document.getElementById('modalAsignarRol')).hide();
      await cargarUsuarios();
    } catch (error) {
      alert(error.message);
    }
  });

  // Foto de perfil: cambiar y eliminar
  const fotoInput = document.getElementById('perfil-foto-input');
  document.getElementById('btn-cambiar-foto').addEventListener('click', () => fotoInput.click());

  fotoInput.addEventListener('change', async () => {
    const archivo = fotoInput.files[0];
    if (!archivo) return;
    const u = USUARIOS.find((x) => x.id === usuarioSeleccionado) || USUARIOS[0];
    if (!u) return;
    const formData = new FormData();
    formData.append('foto', archivo);
    try {
      const respuesta = await fetch(`/api/usuarios/${u.id}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: formData,
      });
      const cuerpo = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) throw new Error(cuerpo.error || 'No se pudo actualizar la foto.');
      fotoInput.value = '';
      const actualizado = cuerpo.usuario;
      if (actualizado) {
        const idx = USUARIOS.findIndex((x) => x.id === Number(u.id));
        if (idx >= 0) USUARIOS[idx] = actualizado;
        sincronizarNavbarCon(actualizado);
      }
      await cargarUsuarios();
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById('btn-eliminar-foto').addEventListener('click', async () => {
    const u = USUARIOS.find((x) => x.id === usuarioSeleccionado) || USUARIOS[0];
    if (!u || !u.foto_url) return;
    if (!confirm(`¿Eliminar la foto de perfil de ${nombreCompleto(u) || u.usuario}?`)) return;
    try {
      await apiFetch(`/api/usuarios/${u.id}/`, { eliminar_foto: '1' });
      await cargarUsuarios();
      sincronizarNavbarCon(USUARIOS.find((x) => x.id === Number(u.id)));
    } catch (error) {
      alert(error.message);
    }
  });
});
