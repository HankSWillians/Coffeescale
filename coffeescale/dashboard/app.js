// =============================================================
// CoffeeScale Dashboard v2 — Dark Specialty Coffee Bar
// =============================================================

import { fetchDashboardState } from "./api.js";

const state = {
  data: null,
  filter: "all",
};

const el = (id) => document.getElementById(id);

const STATUS_LABEL = {
  ok:       "Operación normal",
  warning:  "Reposición sugerida",
  critical: "Reposición urgente",
};

const ORDER_STATUS_LABEL = {
  procesando: "Procesando",
  confirmada: "Confirmada",
  enviada:    "Enviada",
};

const EVENT_TAG_LABEL = {
  info:     "Telemetría",
  warning:  "Advertencia",
  critical: "Crítico",
  security: "Seguridad",
};

// =============================================================
// Top bar clock
// =============================================================
function tickClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  el("clock").textContent = `${hh}:${mm}:${ss}`;
}

// =============================================================
// KPIs
// =============================================================
function renderKpis() {
  const s = state.data.summary;
  el("kpi-stores").textContent  = s.stores;
  el("kpi-sacks").textContent   = s.sacks;
  el("kpi-alerts").textContent  = s.alerts;
  el("kpi-orders").textContent  = s.ordersToday;
}

// =============================================================
// Stores
// =============================================================
function renderStores() {
  const container = el("stores-grid");
  const filtered = state.data.stores.filter((store) => {
    if (state.filter === "all") return true;
    return store.status === state.filter;
  });
  container.innerHTML = filtered.map(renderStore).join("");
}

function renderStore(store) {
  return `
    <article class="store" data-id="${store.id}">
      <div class="store__header">
        <h3 class="store__name">${store.name}</h3>
        <span class="store__id">${store.id}</span>
      </div>

      <p class="store__location">
        <svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
        ${store.city}<span class="dot">·</span>${store.address}<span class="dot">·</span>${store.altitude} m
      </p>

      <div class="store__status store__status--${store.status}">
        <span class="status-dot"></span>
        <span>${STATUS_LABEL[store.status]}</span>
        <span class="store__sync">sync ${store.lastSync}</span>
      </div>

      <ul class="sacks">
        ${store.sacks.map(renderSack).join("")}
      </ul>
    </article>
  `;
}

function renderSack(sack) {
  const pct = (sack.current / sack.capacity) * 100;
  const thresholdPct = (sack.threshold / sack.capacity) * 100;
  return `
    <li class="sack">
      <div class="sack__head">
        <span class="sack__product">${sack.product}</span>
        <span class="sack__weight">
          ${sack.current.toFixed(1)}<em> / ${sack.capacity} kg</em>
        </span>
      </div>
      <p class="sack__meta">${sack.origin}</p>
      <div class="sack__bar">
        <div class="sack__bar-fill sack__bar-fill--${sack.status}" style="width: ${pct}%"></div>
        <div class="sack__threshold" style="left: ${thresholdPct}%"></div>
      </div>
    </li>
  `;
}

// =============================================================
// Events
// =============================================================
function renderEvents() {
  el("events-list").innerHTML = state.data.recentEvents.map(renderEvent).join("");
}

function renderEvent(event) {
  return `
    <li class="event">
      <span class="event__time">${event.time}</span>
      <div>
        <div class="event__body">
          <span class="event__store">${event.store}</span> · ${event.message}
        </div>
        <span class="event__tag event__tag--${event.severity}">${EVENT_TAG_LABEL[event.severity] || "Evento"}</span>
      </div>
    </li>
  `;
}

// =============================================================
// Orders
// =============================================================
function renderOrders() {
  el("orders-list").innerHTML = state.data.recentOrders.map(renderOrder).join("");
}

function renderOrder(order) {
  return `
    <li class="order">
      <span class="order__id">${order.id}</span>
      <div>
        <p class="order__title">${order.product}</p>
        <p class="order__meta">${order.store} · ${order.quantity} · creada ${order.createdAt}</p>
        <p class="order__status order__status--${order.status}">${ORDER_STATUS_LABEL[order.status]}</p>
      </div>
    </li>
  `;
}

// =============================================================
// Filters
// =============================================================
function setupFilters() {
  document.querySelectorAll(".filter").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      state.filter = btn.dataset.filter;
      renderStores();
    });
  });
}

// =============================================================
// Live event simulation
// =============================================================
const STORE_NAMES = ["Centro", "Chapinero", "Usaquén", "El Poblado", "San Antonio"];
const SACK_NUMBERS = Array.from({ length: 18 }, (_, i) => String(i + 1).padStart(3, "0"));

function fakeNewEvent() {
  const store = STORE_NAMES[Math.floor(Math.random() * STORE_NAMES.length)];
  const sackId = SACK_NUMBERS[Math.floor(Math.random() * SACK_NUMBERS.length)];
  const weight = (Math.random() * 20).toFixed(2);
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

  const event = {
    time,
    store,
    type: "telemetry",
    message: `Saco S-${sackId} actualizó peso a ${weight} kg`,
    severity: "info",
  };

  state.data.recentEvents = [event, ...state.data.recentEvents].slice(0, 8);
  renderEvents();
  const first = document.querySelector("#events-list .event");
  if (first) first.classList.add("event--new");
}

// =============================================================
// Boot
// =============================================================
async function init() {
  tickClock();
  setInterval(tickClock, 1000);

  state.data = await fetchDashboardState();

  renderKpis();
  renderStores();
  renderEvents();
  renderOrders();
  setupFilters();

  // Auto-refresh cada 30 s
  setInterval(async () => {
    state.data = await fetchDashboardState();
    renderKpis();
    renderStores();
    renderOrders();
  }, 30000);

  setInterval(fakeNewEvent, 4500 + Math.random() * 4000);

  el("btn-refresh").addEventListener("click", async () => {
    state.data = await fetchDashboardState();
    renderKpis();
    renderStores();
    renderOrders();
    tickClock();
    fakeNewEvent();
    const btn = el("btn-refresh");
    btn.style.borderColor = "var(--gold-bright)";
    btn.style.color = "var(--gold-bright)";
    setTimeout(() => {
      btn.style.borderColor = "";
      btn.style.color = "";
    }, 400);
  });
}

document.addEventListener("DOMContentLoaded", init);
