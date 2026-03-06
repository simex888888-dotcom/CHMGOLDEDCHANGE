/* =====================================================
   CHM GOLD EXCHANGE — Telegram Mini App
   ===================================================== */

'use strict';

// --------------------------------------------------------------------------
// Telegram WebApp init
// --------------------------------------------------------------------------
const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  // Apply Telegram theme
  document.documentElement.style.setProperty('--bg', tg.themeParams.bg_color || '#ffffff');
  document.documentElement.style.setProperty('--bg-secondary', tg.themeParams.secondary_bg_color || '#f1f1f1');
  document.documentElement.style.setProperty('--text', tg.themeParams.text_color || '#000000');
  document.documentElement.style.setProperty('--text-hint', tg.themeParams.hint_color || '#999999');
  document.documentElement.style.setProperty('--link', tg.themeParams.link_color || '#2481cc');
  document.documentElement.style.setProperty('--button', tg.themeParams.button_color || '#2481cc');
  document.documentElement.style.setProperty('--button-text', tg.themeParams.button_text_color || '#ffffff');
}

// --------------------------------------------------------------------------
// Config
// --------------------------------------------------------------------------
const API_BASE = '';  // Same origin (FastAPI serves frontend)
const DEBOUNCE_MS = 300;

const DIRECTION_META = {
  USD_RUB:  { from: 'USD', to: 'RUB',  dir: 'sell', min: 1000,  label: 'USD → RUB (SWIFT)',   hint: 'Номер счёта или банковские реквизиты' },
  EUR_RUB:  { from: 'EUR', to: 'RUB',  dir: 'sell', min: 1000,  label: 'EUR → RUB (SWIFT)',   hint: 'Номер счёта или банковские реквизиты' },
  USDT_RUB: { from: 'USDT', to: 'RUB', dir: 'sell', min: 100,   label: 'USDT → RUB',          hint: 'Номер карты РФ (16 цифр)' },
  RUB_USDT: { from: 'RUB', to: 'USDT', dir: 'buy',  min: 10000, label: 'RUB → USDT',          hint: 'USDT-кошелёк (TRC-20 или ERC-20)' },
  CASH_RUB: { from: '?',   to: 'RUB',  dir: 'sell', min: 10000, label: 'Получить наличные RUB', hint: 'Опишите пожелания по сумме и срокам' },
};

const STATUS_INFO = {
  pending:     { label: 'Ожидает', cls: 'status-pending',     icon: '⏳' },
  approved:    { label: 'Принята', cls: 'status-approved',    icon: '✅' },
  in_progress: { label: 'В работе', cls: 'status-in_progress', icon: '🔄' },
  completed:   { label: 'Выполнена', cls: 'status-completed',  icon: '✅' },
  cancelled:   { label: 'Отменена', cls: 'status-cancelled',   icon: '❌' },
};

// --------------------------------------------------------------------------
// State
// --------------------------------------------------------------------------
const state = {
  rates: null,
  orders: [],
  currentScreen: 'rates',
  calcDebounce: null,
};

// --------------------------------------------------------------------------
// Utility helpers
// --------------------------------------------------------------------------
function fmt(n, digits = 2) {
  return Number(n).toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function showToast(msg, duration = 2500) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

function getInitData() {
  return tg?.initData || '';
}

async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': getInitData(),
    ...(options.headers || {}),
  };
  const res = await fetch(API_BASE + path, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// --------------------------------------------------------------------------
// App namespace
// --------------------------------------------------------------------------
const App = {

  // ---- Screens ----
  showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.getElementById(`screen-${name}`)?.classList.add('active');
    document.querySelector(`.nav-item[data-screen="${name}"]`)?.classList.add('active');
    state.currentScreen = name;

    // Telegram MainButton
    if (tg?.MainButton) {
      if (name === 'exchange') {
        tg.MainButton.setText('Подать заявку');
        tg.MainButton.show();
        tg.MainButton.onClick(() => App.submitOrder(null));
      } else {
        tg.MainButton.hide();
      }
    }

    // Load data
    if (name === 'rates' && !state.rates) App.loadRates();
    if (name === 'orders') App.loadOrders();
  },

  // ---- Rates screen ----
  async loadRates() {
    const skeleton = document.getElementById('rates-skeleton');
    const content = document.getElementById('rates-content');
    const error = document.getElementById('rates-error');

    skeleton.style.display = 'flex';
    content.style.display = 'none';
    error.style.display = 'none';

    try {
      state.rates = await apiFetch('/api/rates');
      content.innerHTML = App._renderRates(state.rates);
      skeleton.style.display = 'none';
      content.style.display = 'flex';
    } catch (e) {
      skeleton.style.display = 'none';
      error.style.display = 'flex';
      console.error('Failed to load rates:', e);
    }
  },

  _renderRates(rates) {
    const icons = {
      USD_RUB: '🇺🇸', EUR_RUB: '🇪🇺', USDT_RUB: '🔵', RUB_USDT: '🔵', CASH_RUB: '💵',
    };
    return Object.entries(rates).map(([key, r]) => {
      const icon = icons[key] || '💱';
      return `
        <div class="rate-card" onclick="App.selectDirection('${key}')">
          <div class="rate-card-header">
            <span class="rate-card-title">${icon} ${r.label}</span>
            <span class="rate-card-desc">${r.description}</span>
          </div>
          <div class="rate-card-rows">
            <div class="rate-row">
              <span class="rate-row-label">Базовый (CXC):</span>
              <span class="rate-row-value">${fmt(r.base_rate, 2)}</span>
            </div>
            <div class="rate-row">
              <span class="rate-row-label">Наш курс:</span>
              <span class="rate-row-value our">${fmt(r.our_rate, 2)}</span>
            </div>
            <div class="rate-row">
              <span class="rate-row-label">Комиссия:</span>
              <span class="rate-badge">7%</span>
            </div>
            <div class="rate-row">
              <span class="rate-row-label">Мин. сумма:</span>
              <span class="rate-row-value">${fmt(r.min_amount, 0)} ${r.from_currency}</span>
            </div>
          </div>
          <div class="rate-card-action">
            <span class="action-link">Обменять →</span>
          </div>
        </div>
      `;
    }).join('');
  },

  async refreshRates() {
    const btn = document.getElementById('refresh-btn');
    const icon = document.getElementById('refresh-icon');
    btn.disabled = true;
    icon.style.display = 'inline-block';
    btn.classList.add('spinning');
    await App.loadRates();
    btn.disabled = false;
    btn.classList.remove('spinning');
  },

  selectDirection(dir) {
    App.showScreen('exchange');
    const sel = document.getElementById('direction');
    if (sel) {
      sel.value = dir;
      App.onDirectionChange();
    }
  },

  // ---- Exchange form ----
  onDirectionChange() {
    const dir = document.getElementById('direction').value;
    const meta = DIRECTION_META[dir] || {};
    const rates = state.rates || {};
    const rateInfo = rates[dir] || {};

    // Update labels
    document.getElementById('amount-label').textContent = `Сумма (${meta.from || '?'})`;
    document.getElementById('amount-currency').textContent = meta.from || '?';
    document.getElementById('min-amount-hint').textContent =
      `Мин. сумма: ${fmt(meta.min || 0, 0)} ${meta.from || '?'}`;

    // Requisites hint
    document.getElementById('requisites-label').textContent = 'Реквизиты для получения';
    document.getElementById('requisites-hint').textContent = meta.hint || '';

    // City field
    document.getElementById('city-group').style.display = dir === 'CASH_RUB' ? 'block' : 'none';

    // Recalc
    App.onAmountInput();
  },

  onAmountInput() {
    clearTimeout(state.calcDebounce);
    state.calcDebounce = setTimeout(() => App._recalculate(), DEBOUNCE_MS);
  },

  _recalculate() {
    const dir = document.getElementById('direction').value;
    const amountRaw = parseFloat(document.getElementById('amount').value) || 0;
    const meta = DIRECTION_META[dir] || {};
    const rateInfo = (state.rates || {})[dir] || {};
    const calcBlock = document.getElementById('calc-block');
    const submitBtn = document.getElementById('submit-btn');

    if (!amountRaw || !rateInfo.our_rate) {
      calcBlock.style.display = 'none';
      submitBtn.disabled = true;
      return;
    }

    const baseRate = rateInfo.base_rate || 0;
    const ourRate = rateInfo.our_rate || 0;
    const total = amountRaw * ourRate;
    const commission = Math.abs(total - amountRaw * baseRate);

    document.getElementById('calc-base-rate').textContent = `${fmt(baseRate)} ${meta.to || '?'}`;
    document.getElementById('calc-our-rate').textContent = `${fmt(ourRate)} ${meta.to || '?'}`;
    document.getElementById('calc-commission').textContent = `${fmt(commission)} ${meta.to || '?'}`;
    document.getElementById('calc-total').textContent = `${fmt(total)} ${meta.to || '?'}`;

    calcBlock.style.display = 'block';

    const valid = amountRaw >= (meta.min || 0);
    submitBtn.disabled = !valid;

    if (!valid) {
      document.getElementById('min-amount-hint').style.color = 'var(--danger)';
    } else {
      document.getElementById('min-amount-hint').style.color = 'var(--text-hint)';
    }
  },

  async submitOrder(event) {
    if (event) event.preventDefault();

    const dir = document.getElementById('direction').value;
    const amount = parseFloat(document.getElementById('amount').value);
    const requisites = document.getElementById('requisites').value.trim();
    const city = document.getElementById('city').value.trim();
    const meta = DIRECTION_META[dir] || {};
    const errorEl = document.getElementById('form-error');
    const submitBtn = document.getElementById('submit-btn');

    errorEl.style.display = 'none';

    if (!amount || amount < (meta.min || 0)) {
      errorEl.textContent = `Минимальная сумма: ${fmt(meta.min || 0, 0)} ${meta.from}`;
      errorEl.style.display = 'flex';
      return;
    }

    if (!requisites || requisites.length < 5) {
      errorEl.textContent = 'Пожалуйста, укажите реквизиты для получения средств';
      errorEl.style.display = 'flex';
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Отправка...';

    if (tg?.MainButton) {
      tg.MainButton.showProgress(false);
    }

    try {
      const body = { direction: dir, amount_from: amount, requisites };
      if (dir === 'CASH_RUB' && city) body.city = city;

      const order = await apiFetch('/api/orders', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      showToast('✅ Заявка успешно создана!', 3000);
      tg?.HapticFeedback?.notificationOccurred('success');

      // Reset form
      document.getElementById('exchange-form').reset();
      document.getElementById('calc-block').style.display = 'none';
      document.getElementById('city-group').style.display = 'none';

      // Show orders screen
      setTimeout(() => {
        App.showScreen('orders');
        App.loadOrders();
      }, 800);
    } catch (e) {
      errorEl.textContent = `Ошибка: ${e.message}`;
      errorEl.style.display = 'flex';
      tg?.HapticFeedback?.notificationOccurred('error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Подать заявку';
      if (tg?.MainButton) {
        tg.MainButton.hideProgress();
      }
    }
  },

  // ---- Orders screen ----
  async loadOrders() {
    const skeleton = document.getElementById('orders-skeleton');
    const content = document.getElementById('orders-content');
    const empty = document.getElementById('orders-empty');
    const error = document.getElementById('orders-error');

    skeleton.style.display = 'flex';
    content.style.display = 'none';
    empty.style.display = 'none';
    error.style.display = 'none';

    const userId = tg?.initDataUnsafe?.user?.id;
    if (!userId) {
      skeleton.style.display = 'none';
      empty.style.display = 'block';
      return;
    }

    try {
      const orders = await apiFetch(`/api/orders/user/${userId}`);
      state.orders = orders;
      skeleton.style.display = 'none';

      if (!orders.length) {
        empty.style.display = 'block';
      } else {
        content.innerHTML = orders.map(App._renderOrderCard).join('');
        content.style.display = 'flex';
      }
    } catch (e) {
      skeleton.style.display = 'none';
      error.style.display = 'flex';
      console.error('Failed to load orders:', e);
    }
  },

  _renderOrderCard(order) {
    const meta = DIRECTION_META[order.direction] || {};
    const statusInfo = STATUS_INFO[order.status] || { label: order.status, cls: '', icon: '?' };
    const shortId = order.id.substring(0, 8).toUpperCase();
    return `
      <div class="order-card" onclick="App.openOrderModal('${order.id}')">
        <div class="order-card-header">
          <span class="order-id">#${shortId}</span>
          <span class="order-status-badge ${statusInfo.cls}">${statusInfo.icon} ${statusInfo.label}</span>
        </div>
        <div class="order-direction">${meta.label || order.direction}</div>
        <div class="order-amounts">
          ${fmt(order.amount_from)} ${meta.from || '?'} → ${fmt(order.amount_to)} ${meta.to || '?'}
        </div>
        <div class="order-date">${fmtDate(order.created_at)}</div>
      </div>
    `;
  },

  openOrderModal(orderId) {
    const order = state.orders.find(o => o.id === orderId);
    if (!order) return;

    const meta = DIRECTION_META[order.direction] || {};
    const statusInfo = STATUS_INFO[order.status] || { label: order.status, cls: '', icon: '?' };
    const shortId = order.id.substring(0, 8).toUpperCase();

    const html = `
      <div class="order-detail-section">
        <div class="order-detail-title">Информация о заявке</div>
        <div style="text-align:center;margin-bottom:16px;">
          <span class="order-status-badge ${statusInfo.cls}" style="font-size:15px;padding:6px 16px;">
            ${statusInfo.icon} ${statusInfo.label}
          </span>
        </div>
        <div class="order-detail-row"><span class="label">ID заявки</span><span class="value">#${shortId}</span></div>
        <div class="order-detail-row"><span class="label">Направление</span><span class="value">${meta.label || order.direction}</span></div>
        <div class="order-detail-row"><span class="label">Отдаёте</span><span class="value">${fmt(order.amount_from)} ${meta.from || '?'}</span></div>
        <div class="order-detail-row"><span class="label">Получаете</span><span class="value">${fmt(order.amount_to)} ${meta.to || '?'}</span></div>
        <div class="order-detail-row"><span class="label">Курс</span><span class="value">${fmt(order.our_rate)}</span></div>
        <div class="order-detail-row"><span class="label">Комиссия (7%)</span><span class="value">${fmt(order.commission)} ${meta.to || '?'}</span></div>
        <div class="order-detail-row"><span class="label">Реквизиты</span><span class="value">${order.requisites}</span></div>
        ${order.city ? `<div class="order-detail-row"><span class="label">Город</span><span class="value">${order.city}</span></div>` : ''}
        ${order.admin_note ? `<div class="order-detail-row"><span class="label">Комментарий</span><span class="value">${order.admin_note}</span></div>` : ''}
        <div class="order-detail-row"><span class="label">Создана</span><span class="value">${fmtDate(order.created_at)}</span></div>
      </div>

      <div class="order-detail-section">
        <div class="order-detail-title">История статусов</div>
        <div class="timeline">
          ${App._renderTimeline(order)}
        </div>
      </div>
    `;

    document.getElementById('modal-body').innerHTML = html;
    document.getElementById('order-modal').style.display = 'flex';
    document.getElementById('support-link').href = 'https://t.me/chmgold_support';
  },

  _renderTimeline(order) {
    const steps = [
      { status: 'pending',     label: 'Заявка создана',      date: order.created_at },
      { status: 'approved',    label: 'Заявка принята',       date: order.status === 'approved' || order.status === 'in_progress' || order.status === 'completed' ? order.updated_at : null },
      { status: 'in_progress', label: 'Обработка начата',     date: order.status === 'in_progress' || order.status === 'completed' ? order.updated_at : null },
      { status: 'completed',   label: 'Операция выполнена',   date: order.status === 'completed' ? order.updated_at : null },
    ];

    const cancelled = order.status === 'cancelled';
    if (cancelled) {
      steps.push({ status: 'cancelled', label: 'Заявка отменена', date: order.updated_at });
    }

    const currentIdx = steps.findIndex(s => s.status === order.status);

    return steps.map((step, i) => {
      const done = i <= currentIdx;
      const dotCls = done ? (step.status === 'cancelled' ? 'cancelled' : step.status === 'completed' ? 'completed' : '') : 'pending';
      return `
        <div class="timeline-item">
          <div class="timeline-dot ${dotCls}" style="${done ? '' : 'background:var(--border);'}">
            ${done ? '✓' : ''}
          </div>
          <div class="timeline-body">
            <div class="timeline-label" style="${done ? '' : 'color:var(--text-hint);'}">${step.label}</div>
            ${step.date ? `<div class="timeline-date">${fmtDate(step.date)}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  },

  closeOrderModal() {
    document.getElementById('order-modal').style.display = 'none';
  },
};

// --------------------------------------------------------------------------
// Init
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  App.showScreen('rates');
  App.onDirectionChange();

  // Pull-to-refresh on rates screen
  let startY = 0;
  const ratesScreen = document.getElementById('screen-rates');

  ratesScreen.addEventListener('touchstart', e => {
    startY = e.touches[0].clientY;
  }, { passive: true });

  ratesScreen.addEventListener('touchend', e => {
    const dy = e.changedTouches[0].clientY - startY;
    if (dy > 80 && ratesScreen.scrollTop === 0) {
      App.refreshRates();
    }
  }, { passive: true });

  // Back button handling
  if (tg) {
    tg.BackButton.onClick(() => {
      if (document.getElementById('order-modal').style.display !== 'none') {
        App.closeOrderModal();
        tg.BackButton.show();
      } else if (state.currentScreen !== 'rates') {
        App.showScreen('rates');
        tg.BackButton.hide();
      }
    });
  }
});

// Expose App globally
window.App = App;
