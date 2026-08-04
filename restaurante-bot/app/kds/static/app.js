// KDS dashboard client: live orders (WebSocket), order history and menu editing.
const ordersEl = document.getElementById('orders');
const emptyEl = document.getElementById('empty');
const countPendingEl = document.getElementById('count-pending');
const countPreparingEl = document.getElementById('count-preparing');
const historyListEl = document.getElementById('history-list');
const historyEmptyEl = document.getElementById('history-empty');
const menuRootEl = document.getElementById('menu-root');

const orders = new Map(); // order.id -> order (dict from server)
let menuData = { restaurant_name: '', sections: [] };
let ws;

const views = {
  orders: document.getElementById('view-orders'),
  history: document.getElementById('view-history'),
  menu: document.getElementById('view-menu'),
};

function switchView(name) {
  Object.entries(views).forEach(([key, el]) => el.classList.toggle('hidden', key !== name));
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.view === name);
  });
  if (name === 'history') loadHistory();
  if (name === 'menu') loadMenu();
}

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => switchView(tab.dataset.view));
});
document.getElementById('history-refresh').addEventListener('click', loadHistory);

const menuRebuildBtn = document.getElementById('menu-rebuild');
const menuRefreshBtn = document.getElementById('menu-refresh');
const menuRebuildStatus = document.getElementById('menu-rebuild-status');

function setRebuildStatus(message, cls) {
  menuRebuildStatus.textContent = message;
  menuRebuildStatus.className = `menu-rebuild-status ${cls || ''}`;
}

async function postRebuildIndex() {
  const res = await fetch('/menu/rebuild-index', { method: 'POST' });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

function rebuildStatusMessage(res, data) {
  if (res.ok) {
    return { text: `Índice reconstruido: ${data.docs} documentos`, cls: 'ok' };
  }
  if (res.status === 400) {
    return { text: (data && data.error) || 'Error al reconstruir el índice', cls: 'warn' };
  }
  return { text: `Error: ${(data && data.error) || res.status}`, cls: 'err' };
}

async function rebuildMenuIndex() {
  menuRebuildBtn.disabled = true;
  setRebuildStatus('Reconstruyendo índice...', 'info');
  try {
    const { res, data } = await postRebuildIndex();
    const { text, cls } = rebuildStatusMessage(res, data);
    setRebuildStatus(text, cls);
  } catch (e) {
    setRebuildStatus(`Error: ${e.message}`, 'err');
  } finally {
    menuRebuildBtn.disabled = false;
  }
}

async function refreshMenuAndIndex() {
  menuRefreshBtn.disabled = true;
  setRebuildStatus('Actualizando menú e índice...', 'info');
  try {
    const { res, data } = await postRebuildIndex();
    if (res.ok) {
      setRebuildStatus(
        `Menú e índice actualizados ✅ (índice: ${data.docs} documentos)`,
        'ok'
      );
    } else {
      const { text, cls } = rebuildStatusMessage(res, data);
      setRebuildStatus(text, cls);
    }
  } catch (e) {
    setRebuildStatus(`Error: ${e.message}`, 'err');
  } finally {
    menuRefreshBtn.disabled = false;
  }
  loadMenu();
}

menuRebuildBtn.addEventListener('click', rebuildMenuIndex);
menuRefreshBtn.addEventListener('click', refreshMenuAndIndex);

// ---------------------------------------------------------------------------
// Live orders (WebSocket) — unchanged behavior, blink driven by CSS/status.
// ---------------------------------------------------------------------------
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => console.log('KDS conectado al servidor');
  ws.onclose = () => setTimeout(connect, 2000);
  ws.onerror = () => ws.close();
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'init') {
      msg.orders.forEach((o) => orders.set(o.id, o));
      render();
    } else if (msg.type === 'order.created') {
      orders.set(msg.order.id, msg.order);
      render();
      newOrderChime();
    } else if (msg.type === 'order.updated') {
      orders.set(msg.order.id, msg.order);
      render();
    } else if (msg.type === 'order.deleted') {
      orders.delete(msg.order_id);
      render();
    }
  };
}

function formatMoney(value) {
  const n = Number(value);
  const decimals = Number.isInteger(n) ? 0 : 2;
  const formatted = n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `₡${formatted}`;
}

function elapsed(iso) {
  const ms = Math.max(0, Date.now() - new Date(iso).getTime());
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function sendStatus(orderId, status) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'status.change', order_id: orderId, status }));
  }
}

function statusButton(order, status, label, cls) {
  const button = document.createElement('button');
  button.className = `btn ${cls}`;
  button.textContent = label;
  button.onclick = () => sendStatus(order.id, status);
  return button;
}

function deleteButton(order) {
  const button = document.createElement('button');
  button.className = 'btn ghost danger';
  button.textContent = 'Borrar';
  button.onclick = () => deleteOrder(order.id);
  return button;
}

async function deleteOrder(orderId) {
  const cardEl = document.querySelector(`.card[data-id="${orderId}"]`);
  try {
    const res = await fetch(`/orders/${orderId}`, { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error((data && data.error) || `HTTP ${res.status}`);
    }
  } catch (e) {
    console.error(`No se pudo borrar el pedido #${orderId}:`, e);
    if (cardEl) {
      const errorNote = document.createElement('div');
      errorNote.className = 'meta';
      errorNote.textContent = `Error al borrar: ${e.message}`;
      cardEl.querySelector('.actions').appendChild(errorNote);
    }
    return;
  }
  orders.delete(orderId);
  render();
}

function card(order) {
  const div = document.createElement('div');
  div.className = `card status-${order.status}`;
  div.dataset.id = order.id;

  const head = document.createElement('div');
  head.className = 'card-head';

  const number = document.createElement('div');
  number.className = 'number';
  number.textContent = `#${order.number}`;

  const time = document.createElement('div');
  time.className = 'time';
  time.textContent = elapsed(order.created_at);
  head.append(number, time);

  const badges = document.createElement('div');
  badges.className = 'badges';
  const badge = document.createElement('div');
  badge.className = 'badge';
  badge.textContent = order.status_label;
  badges.appendChild(badge);
  if (order.status === 'pending') {
    const nuevo = document.createElement('div');
    nuevo.className = 'badge new-badge';
    nuevo.textContent = '¡NUEVO!';
    badges.appendChild(nuevo);
  }

  const items = document.createElement('div');
  items.className = 'items';
  order.items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'item';
    row.textContent = `${item.quantity} × ${item.name}  ${formatMoney(item.total)}`;
    items.appendChild(row);
  });

  const foot = document.createElement('div');
  foot.className = 'card-foot';

  const meta = document.createElement('div');
  meta.className = 'meta';
  const deliveryIcon = order.delivery_type === 'delivery' ? '🛵 Delivery' : '🏪 Pickup';
  meta.textContent = order.customer_name
    ? `${deliveryIcon} · Cliente: ${order.customer_name}`
    : deliveryIcon;
  foot.appendChild(meta);

  if (order.delivery_type === 'delivery' && (order.delivery_phone || order.delivery_address)) {
    const deliveryMeta = document.createElement('div');
    deliveryMeta.className = 'meta meta-delivery';
    const parts = [];
    if (order.delivery_phone) parts.push(`📞 ${order.delivery_phone}`);
    if (order.delivery_address) parts.push(`📍 ${order.delivery_address}`);
    deliveryMeta.textContent = parts.join(' · ');
    foot.appendChild(deliveryMeta);
  }

  const total = document.createElement('div');
  total.className = 'total';
  total.textContent = formatMoney(order.total);
  foot.append(total);

  const actions = document.createElement('div');
  actions.className = 'actions';
  if (order.status === 'pending') {
    actions.appendChild(statusButton(order, 'preparing', 'En preparación', 'primary'));
    actions.appendChild(statusButton(order, 'completed', 'Completar', 'done'));
  } else if (order.status === 'preparing') {
    actions.appendChild(statusButton(order, 'completed', '✓ Completada', 'done'));
    actions.appendChild(statusButton(order, 'pending', 'Volver a pendiente', 'ghost'));
  } else {
    actions.appendChild(statusButton(order, 'pending', 'Volver a pendiente', 'ghost'));
    if (order.status === 'completed') {
      actions.appendChild(deleteButton(order));
    }
  }

  div.append(head, badges, items, foot, actions);
  return div;
}

function render() {
  const list = [...orders.values()].sort((a, b) => a.created_at.localeCompare(b.created_at));
  ordersEl.innerHTML = '';
  list.forEach((order) => ordersEl.appendChild(card(order)));

  emptyEl.style.display = list.length ? 'none' : 'block';
  const pending = list.filter((o) => o.status === 'pending').length;
  const preparing = list.filter((o) => o.status === 'preparing').length;
  countPendingEl.textContent = `Pendientes: ${pending}`;
  countPreparingEl.textContent = `En preparación: ${preparing}`;
}

// ---------------------------------------------------------------------------
// New-order chime: two-tone bell (Uber Eats / PedidosYa style), with a
// persistent mute toggle. Browsers only allow audio after a user gesture,
// so the AudioContext is created lazily on the first click/keypress.
// ---------------------------------------------------------------------------
let audioCtx = null;
let soundEnabled = localStorage.getItem('kds.sound.enabled') !== '0';

const soundToggleEl = document.getElementById('sound-toggle');
function updateSoundToggle() {
  soundToggleEl.textContent = soundEnabled ? '🔊' : '🔇';
  soundToggleEl.title = soundEnabled
    ? 'Silenciar el sonido de pedidos nuevos'
    : 'Activar el sonido de pedidos nuevos';
}
soundToggleEl.addEventListener('click', () => {
  soundEnabled = !soundEnabled;
  localStorage.setItem('kds.sound.enabled', soundEnabled ? '1' : '0');
  updateSoundToggle();
});
updateSoundToggle();

function ensureAudio() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    // Called from a user gesture (click/keypress), so this succeeds.
    audioCtx.resume();
  }
  return audioCtx;
}

// Chrome/Edge unlock audio on the first user gesture anywhere in the page.
document.addEventListener('click', ensureAudio, { once: true });
document.addEventListener('keydown', ensureAudio, { once: true });

function playTone(ctx, freq, start, duration, volume) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(start);
  osc.stop(start + duration + 0.05);
}

// "Ding-ding": two bell strikes (E6 then A5), each with a harmonic overtone
// so it reads as a kitchen order alert instead of a plain beep. It repeats a
// few times so the kitchen doesn't miss the order in a noisy environment.
const CHIME_REPEATS = 3;
const CHIME_REPEAT_GAP = 1.2; // seconds between repetitions

function newOrderChime() {
  if (!soundEnabled) return;
  try {
    const ctx = ensureAudio();
    if (!ctx) return;
    const now = ctx.currentTime + 0.05;
    for (let i = 0; i < CHIME_REPEATS; i++) {
      const t = now + i * CHIME_REPEAT_GAP;
      playTone(ctx, 1318.5, t, 0.35, 0.25);          // E6
      playTone(ctx, 2637.0, t, 0.22, 0.08);          // harmonic
      playTone(ctx, 880.0, t + 0.3, 0.5, 0.18);      // A5 body
      playTone(ctx, 1760.0, t + 0.3, 0.3, 0.07);     // harmonic
    }
  } catch (e) {
    // Audio is not available: ignore.
  }
}

// ---------------------------------------------------------------------------
// History tab: search by day + free text + status, and clear-day button.
// ---------------------------------------------------------------------------
const historyDateEl = document.getElementById('history-date');
const historyQEl = document.getElementById('history-q');
const historyStatusEl = document.getElementById('history-status');
const historyCounterEl = document.getElementById('history-counter');
const historyClearMsgEl = document.getElementById('history-clear-msg');

function todayInputValue() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function formatHistoryDate(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function durationText(seconds) {
  const total = Math.max(0, seconds);
  if (total < 60) return `${total}s`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}min ${s}s`;
}

function itemsSummary(items) {
  return items.map((i) => `${i.quantity} × ${i.name}`).join(', ');
}

function historyQueryString() {
  const params = new URLSearchParams();
  params.set('date', historyDateEl.value || todayInputValue());
  const q = historyQEl.value.trim();
  if (q) params.set('q', q);
  const status = historyStatusEl.value;
  if (status) params.set('status', status);
  params.set('limit', '100');
  return params.toString();
}

async function loadHistory() {
  try {
    const res = await fetch(`/orders/history?${historyQueryString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderHistory(data);
  } catch (e) {
    historyListEl.innerHTML = '<p class="hint">No pude cargar el historial.</p>';
  }
}

function renderHistory(data) {
  const orders = data.orders || [];
  historyCounterEl.textContent =
    `Mostrando los primeros ${orders.length} de ${data.total} pedidos (día: ${formatHistoryDate(data.date)})`;
  historyListEl.innerHTML = '';
  historyEmptyEl.classList.toggle('hidden', orders.length > 0);
  if (!orders.length) return;

  const table = document.createElement('table');
  table.className = 'history-table';
  const thead = document.createElement('thead');
  thead.innerHTML = `
    <tr>
      <th>#</th>
      <th>Cliente</th>
      <th>Ítems</th>
      <th>Total</th>
      <th>Entrega</th>
      <th>Estado</th>
      <th>Fin/Hora</th>
      <th>Duración</th>
    </tr>`;
  const tbody = document.createElement('tbody');
  orders.forEach((h) => tbody.appendChild(historyRow(h)));
  table.append(thead, tbody);
  historyListEl.appendChild(table);
}

function deliveryCell(h) {
  if (h.delivery_type !== 'delivery') return '🏪 Pickup';
  const extras = [];
  if (h.delivery_phone) extras.push(`📞 ${escapeHtml(h.delivery_phone)}`);
  if (h.delivery_address) extras.push(`📍 ${escapeHtml(h.delivery_address)}`);
  if (!extras.length) return '🛵 Delivery';
  return `🛵 Delivery<br><span class="history-meta">${extras.join(' · ')}</span>`;
}

function historyRow(h) {
  const tr = document.createElement('tr');
  const finished = new Date(h.updated_at).toLocaleString('es-AR', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
  const statusPill =
    `<span class="status-pill ${escapeHtml(h.status)}">${escapeHtml(h.status_label || 'Completada')}</span>`;
  tr.innerHTML = `
    <td class="history-number-cell">#${h.number}</td>
    <td>${escapeHtml(h.customer_name || '—')}</td>
    <td class="history-items-cell">${escapeHtml(itemsSummary(h.items))}</td>
    <td class="history-total-cell">${formatMoney(h.total)}</td>
    <td>${deliveryCell(h)}</td>
    <td>${statusPill}</td>
    <td>${finished}</td>
    <td>${durationText(h.duration_seconds)}</td>`;
  return tr;
}

let historySearchTimer = null;
historyQEl.addEventListener('input', () => {
  clearTimeout(historySearchTimer);
  historySearchTimer = setTimeout(loadHistory, 300);
});
historyDateEl.addEventListener('change', loadHistory);
historyStatusEl.addEventListener('change', loadHistory);
document.getElementById('history-search').addEventListener('click', loadHistory);

async function clearDayOrders() {
  const day = historyDateEl.value || todayInputValue();
  const formatted = formatHistoryDate(day);
  const confirmed = confirm(
    `¿Borrar TODOS los pedidos del día ${formatted}?\n\n` +
    'Esta acción es permanente y no se puede deshacer. ¿Continuar?'
  );
  if (!confirmed) return;
  try {
    const res = await fetch('/orders/clear-day', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: day }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
    historyClearMsgEl.textContent = `Se borraron ${data.deleted} pedido(s) del día ${formatted}.`;
    historyClearMsgEl.className = 'history-clear-msg ok';
    await loadHistory();
  } catch (e) {
    historyClearMsgEl.textContent = `No pude borrar los pedidos: ${e.message}`;
    historyClearMsgEl.className = 'history-clear-msg err';
  }
}

document.getElementById('history-clear-day').addEventListener('click', clearDayOrders);

// ---------------------------------------------------------------------------
// Menu tab
// ---------------------------------------------------------------------------
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function apiJson(url, method, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${url} -> ${res.status}`);
  return res.json();
}

async function loadMenu() {
  try {
    const res = await fetch('/menu');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    menuData = await res.json();
    renderMenu();
  } catch (e) {
    menuRootEl.innerHTML = '<p class="hint">No pude cargar el menú.</p>';
  }
}

function renderMenu() {
  menuRootEl.innerHTML = '';

  // Add-section tool
  const addSection = document.createElement('div');
  addSection.className = 'menu-tool';
  addSection.innerHTML = `
    <h3>Agregar sección</h3>
    <div class="menu-form-row">
      <input id="new-section-name" placeholder="Nombre de la sección" />
      <button class="btn primary" id="add-section-btn">Agregar sección</button>
    </div>`;
  menuRootEl.appendChild(addSection);
  document.getElementById('add-section-btn').onclick = async () => {
    const name = document.getElementById('new-section-name').value.trim();
    if (!name) return;
    await apiJson('/menu/sections', 'POST', { name });
    document.getElementById('new-section-name').value = '';
    loadMenu();
  };

  // Add-item tool
  const addItem = document.createElement('div');
  addItem.className = 'menu-tool';
  addItem.innerHTML = `
    <h3>Agregar ítem</h3>
    <div class="menu-form-row">
      <select id="new-item-section">
        ${menuData.sections.map((s) => `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)}</option>`).join('')}
      </select>
      <input id="new-item-name" placeholder="Nombre" />
      <input id="new-item-price" type="number" step="0.01" placeholder="Precio" />
      <input id="new-item-desc" placeholder="Descripción" />
      <button class="btn primary" id="add-item-btn">Agregar ítem</button>
    </div>`;
  menuRootEl.appendChild(addItem);
  document.getElementById('add-item-btn').onclick = async () => {
    const section = document.getElementById('new-item-section').value;
    const name = document.getElementById('new-item-name').value.trim();
    const price = parseFloat(document.getElementById('new-item-price').value) || 0;
    const description = document.getElementById('new-item-desc').value.trim();
    if (!section || !name) return;
    await apiJson('/menu/items', 'POST', { section, name, price, description });
    loadMenu();
  };

  // Sections
  if (!menuData.sections.length) {
    const empty = document.createElement('p');
    empty.className = 'hint';
    empty.textContent = 'El menú no tiene secciones todavía.';
    menuRootEl.appendChild(empty);
  }
  menuData.sections.forEach((section) => menuRootEl.appendChild(sectionBlock(section)));
}

function sectionBlock(section) {
  const block = document.createElement('div');
  block.className = 'menu-section';

  const head = document.createElement('div');
  head.className = 'menu-section-head';
  const title = document.createElement('h3');
  title.textContent = section.name;
  const del = document.createElement('button');
  del.className = 'btn ghost';
  del.textContent = 'Eliminar sección';
  del.onclick = async () => {
    if (!confirm(`¿Eliminar la sección "${section.name}" y todos sus ítems?`)) return;
    await apiJson(`/menu/sections/${encodeURIComponent(section.name)}`, 'DELETE');
    loadMenu();
  };
  head.append(title, del);
  block.appendChild(head);

  const items = document.createElement('div');
  items.className = 'menu-items';
  if (!section.items.length) {
    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = 'Sin ítems.';
    items.appendChild(hint);
  } else {
    section.items.forEach((item) => items.appendChild(itemRow(section, item)));
  }
  block.appendChild(items);
  return block;
}

function itemRow(section, item) {
  const row = document.createElement('div');
  row.className = 'menu-item-row';
  row.dataset.itemId = item.id;

  const info = document.createElement('div');
  info.className = 'menu-item-info';
  info.innerHTML = `
    <div class="menu-item-name">${escapeHtml(item.name)} <span class="menu-item-price">${formatMoney(item.price)}</span></div>
    <div class="menu-item-desc">${escapeHtml(item.description || '')}</div>`;

  const actions = document.createElement('div');
  actions.className = 'menu-item-actions';
  const editBtn = document.createElement('button');
  editBtn.className = 'btn primary';
  editBtn.textContent = 'Editar';
  editBtn.onclick = () => startEdit(row, section, item);
  const delBtn = document.createElement('button');
  delBtn.className = 'btn ghost';
  delBtn.textContent = 'Eliminar';
  delBtn.onclick = async () => {
    if (!confirm(`¿Eliminar "${item.name}"?`)) return;
    await apiJson(`/menu/items/${encodeURIComponent(item.id)}`, 'DELETE');
    loadMenu();
  };
  actions.append(editBtn, delBtn);
  row.append(info, actions);
  return row;
}

function startEdit(row, section, item) {
  row.classList.add('editing');
  row.innerHTML = `
    <div class="menu-form-row menu-edit-form">
      <select class="edit-section">
        ${menuData.sections.map((s) => `<option value="${escapeHtml(s.name)}" ${s.name === section.name ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('')}
      </select>
      <input class="edit-name" value="${escapeHtml(item.name)}" placeholder="Nombre" />
      <input class="edit-price" type="number" step="0.01" value="${item.price}" placeholder="Precio" />
      <input class="edit-desc" value="${escapeHtml(item.description || '')}" placeholder="Descripción" />
      <button class="btn primary save">Guardar</button>
      <button class="btn ghost cancel">Cancelar</button>
    </div>`;
  row.querySelector('.save').onclick = async () => {
    const body = {
      section: row.querySelector('.edit-section').value,
      name: row.querySelector('.edit-name').value.trim(),
      price: parseFloat(row.querySelector('.edit-price').value) || 0,
      description: row.querySelector('.edit-desc').value.trim(),
    };
    await apiJson(`/menu/items/${encodeURIComponent(item.id)}`, 'PUT', body);
    loadMenu();
  };
  row.querySelector('.cancel').onclick = () => loadMenu();
}

// ---------------------------------------------------------------------------
// Menu PDF upload: stage a PDF, confirm, then replace the whole menu.
// ---------------------------------------------------------------------------
const menuPdfInput = document.getElementById('menu-pdf-input');
const menuPdfUploadBtn = document.getElementById('menu-pdf-upload');
const menuPdfStatus = document.getElementById('menu-pdf-status');
let pendingMenuToken = null;

function setPdfStatus(message, cls) {
  menuPdfStatus.textContent = message;
  menuPdfStatus.className = `menu-pdf-status ${cls || ''}`;
}

function setPdfStatusHtml(html, cls) {
  menuPdfStatus.innerHTML = html;
  menuPdfStatus.className = `menu-pdf-status ${cls || ''}`;
}

async function uploadMenuPdf() {
  const file = menuPdfInput.files && menuPdfInput.files[0];
  if (!file) {
    setPdfStatus('Elegí un archivo PDF primero.', 'warn');
    return;
  }
  menuPdfUploadBtn.disabled = true;
  setPdfStatus('Procesando PDF...', 'info');
  try {
    const formData = new FormData();
    formData.append('file', file);
    // Multipart upload: FormData sets its own Content-Type boundary, so no
    // explicit header (unlike the JSON apiJson helper).
    const res = await fetch('/menu/upload-pdf', { method: 'POST', body: formData });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setPdfStatus((data && data.error) || `Error: HTTP ${res.status}`, 'err');
      return;
    }
    pendingMenuToken = data.token;
    const examples = (data.examples || []).map(escapeHtml).join(' · ');
    let html = `Encontré ${data.sections} secciones y ${data.items} ítems (ej. ${examples}).<br>¿Reemplazo todo el menú actual?`;
    if (data.used_llm === false) {
      html += `<br><span class="menu-pdf-warn">⚠️ Sin OPENAI_API_KEY el texto se extrajo sin limpiar; el menú puede necesitar revisión manual.</span>`;
    }
    html += `<div class="menu-pdf-actions">
      <button class="btn primary" id="menu-pdf-confirm">✅ Sí, reemplazar</button>
      <button class="btn danger" id="menu-pdf-cancel">❌ Cancelar</button>
    </div>`;
    setPdfStatusHtml(html, 'ok');
    document.getElementById('menu-pdf-confirm').onclick = applyMenuUpload;
    document.getElementById('menu-pdf-cancel').onclick = cancelMenuUpload;
  } catch (e) {
    setPdfStatus(`Error: ${e.message}`, 'err');
  } finally {
    menuPdfUploadBtn.disabled = false;
  }
}

async function applyMenuUpload() {
  if (!pendingMenuToken) return;
  try {
    const data = await apiJson('/menu/apply-upload', 'POST', { token: pendingMenuToken });
    pendingMenuToken = null;
    menuPdfInput.value = '';
    if (data.rag_rebuilt) {
      setPdfStatus('¡Menú actualizado! Índice RAG reconstruido.', 'ok');
    } else {
      setPdfStatus('¡Menú actualizado! No se pudo reconstruir el índice RAG (falta OPENAI_API_KEY). Cuando configures la clave, usá el botón "Actualizar menú" para reconstruirlo automáticamente.', 'warn');
    }
    loadMenu();
  } catch (e) {
    setPdfStatus(`Error: ${e.message}`, 'err');
  }
}

async function cancelMenuUpload() {
  if (!pendingMenuToken) return;
  try {
    await apiJson('/menu/cancel-upload', 'POST', { token: pendingMenuToken });
  } catch (e) {
    // Ignore network errors; the pending token is discarded server-side anyway.
  }
  pendingMenuToken = null;
  menuPdfInput.value = '';
  setPdfStatus('Ok, no cambié nada.', 'warn');
}

menuPdfUploadBtn.addEventListener('click', uploadMenuPdf);

// ---------------------------------------------------------------------------
// Clock
// ---------------------------------------------------------------------------
function tick() {
  document.getElementById('clock').textContent = new Date().toLocaleString('es-AR', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  });
  document.querySelectorAll('.time').forEach((timeEl) => {
    const cardEl = timeEl.closest('.card');
    if (!cardEl) return;
    const order = orders.get(Number(cardEl.dataset.id));
    if (order) timeEl.textContent = elapsed(order.created_at);
  });
}

setInterval(tick, 1000);
connect();
