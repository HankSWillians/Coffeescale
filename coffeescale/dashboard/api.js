// =============================================================
// CoffeeScale Dashboard — API client
// Conecta al backend desplegado en AWS o cae a MOCK_DATA si falla.
// =============================================================

import MOCK_DATA from "./mock-data.js";

// URL del DashboardEndpoint del stack desplegado en us-east-1.
// Para apuntar a otro endpoint, basta cambiar esta constante.
const DASHBOARD_ENDPOINT =
  "https://vdef0jhgal.execute-api.us-east-1.amazonaws.com/prod/dashboard/state";

// Catálogo de tiendas para enriquecer la respuesta del backend con metadata
// (nombre, ciudad, dirección...) que el backend no devuelve pero el dashboard
// necesita renderizar. La fuente de verdad de números (peso, status) sigue
// siendo el backend.
const STORE_METADATA = {
  "CS-001": { name: "Centro",          city: "Bogotá",     address: "Cra. 7 # 14 — 22",       altitude: 2640, manager: "Lucía Gómez" },
  "CS-002": { name: "Chapinero",       city: "Bogotá",     address: "Cl. 67 # 9 — 30",        altitude: 2670, manager: "Andrés Pinto" },
  "CS-003": { name: "Usaquén",         city: "Bogotá",     address: "Cra. 6 # 119 — 50",      altitude: 2700, manager: "Camila Reyes" },
  "CS-004": { name: "El Poblado",      city: "Medellín",   address: "Cl. 10 # 38 — 12",       altitude: 1500, manager: "Mateo Vélez" },
  "CS-005": { name: "San Antonio",     city: "Cali",       address: "Cra. 5 # 5 — 18",        altitude: 1000, manager: "Sofía Quintero" },
};

/**
 * Calcula tiempo relativo legible ("hace 12 s", "hace 3 min") a partir
 * de un ISO timestamp.
 */
function formatRelative(isoTimestamp) {
  if (!isoTimestamp) return "—";
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 60) return `hace ${sec} s`;
  const min = Math.round(sec / 60);
  if (min < 60) return `hace ${min} min`;
  const hr = Math.round(min / 60);
  return `hace ${hr} h`;
}

/**
 * Mapea la respuesta del backend al shape que el dashboard espera.
 */
function adaptBackendResponse(backend) {
  const stores = (backend.stores || []).map((store) => {
    const meta = STORE_METADATA[store.storeId] || {
      name: store.storeId,
      city: "—",
      address: "—",
      altitude: 0,
      manager: "—",
    };

    // Calcular lastSync: el timestamp más reciente entre los sacos
    const timestamps = (store.sacks || []).map((s) => s.timestamp).filter(Boolean);
    const mostRecent = timestamps.sort().pop();

    return {
      id: store.storeId,
      name: meta.name,
      city: meta.city,
      address: meta.address,
      altitude: meta.altitude,
      manager: meta.manager,
      status: store.status,
      lastSync: formatRelative(mostRecent),
      sacks: (store.sacks || []).map((s) => ({
        id: s.deviceId,
        product: s.product,
        origin: s.product, // backend no trae origin separado; reutilizamos product
        capacity: s.capacityKg,
        current: s.currentKg,
        threshold: s.thresholdKg,
        status: s.status,
      })),
    };
  });

  const totalSacks = stores.reduce((acc, s) => acc + s.sacks.length, 0);
  const alerts = stores.reduce(
    (acc, s) => acc + s.sacks.filter((k) => k.status !== "ok").length,
    0
  );

  // Adaptar órdenes del backend al formato del dashboard
  const recentOrders = (backend.recentOrders || []).map((o) => ({
    id: o.orderId || o.id || "—",
    product: o.product || "—",
    store: o.storeId || "—",
    quantity: o.quantity ? `${o.quantity} kg` : "—",
    createdAt: formatRelative(o.createdAt),
    status: o.status || "procesando",
  }));

  return {
    meta: {
      edition: "Live",
      issue: "Producción",
      date: new Date().toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }),
      lastUpdate: new Date().toISOString(),
    },
    summary: {
      stores: stores.length,
      sacks: totalSacks,
      alerts,
      ordersToday: recentOrders.length,
      monthlyUptime: "99.94%",
      monthlyCost: "$0.14",
    },
    stores,
    // El backend no tiene historial de eventos (decisión arquitectónica: sin histórico).
    // Mantenemos el array vacío; app.js los genera localmente en vivo.
    recentEvents: [],
    recentOrders,
  };
}

/**
 * Obtiene el estado actual del dashboard:
 * - intenta el endpoint real
 * - si falla, usa los datos mock como fallback (modo desarrollo)
 */
export async function fetchDashboardState() {
  try {
    const response = await fetch(DASHBOARD_ENDPOINT, {
      method: "GET",
      headers: { "Accept": "application/json" },
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const backend = await response.json();
    console.log("[CoffeeScale] Datos del backend cargados", backend);
    return adaptBackendResponse(backend);
  } catch (err) {
    console.warn("[CoffeeScale] Backend no disponible, usando MOCK_DATA:", err.message);
    return MOCK_DATA;
  }
}