// =============================================================
// CoffeeScale — Datos Mock (MVP)
// Reemplazar por llamadas reales a la API una vez desplegado el backend
// =============================================================

const MOCK_DATA = {
  meta: {
    edition: 'Vol. I',
    issue: 'No. 5',
    date: '18 de mayo, 2026',
    lastUpdate: new Date().toISOString(),
  },

  summary: {
    stores: 5,
    sacks: 18,
    alerts: 3,
    ordersToday: 4,
    monthlyUptime: '99.94%',
    monthlyCost: '$0.14',
  },

  stores: [
    {
      id: 'CS-001',
      name: 'Centro',
      city: 'Bogotá',
      address: 'Cra. 7 # 14 — 22',
      altitude: 2640,
      manager: 'Lucía Gómez',
      status: 'ok',
      lastSync: 'hace 12 s',
      sacks: [
        { id: 'S-001', product: 'Andina Origen — Espresso Blend', origin: 'Huila + Antioquia', capacity: 20, current: 14.6, threshold: 5.0, status: 'ok' },
        { id: 'S-002', product: 'Casa Espresso Profundo',          origin: 'Tolima',             capacity: 20, current: 11.8, threshold: 5.0, status: 'ok' },
        { id: 'S-003', product: 'Cauca Decaf — Swiss Water',       origin: 'Cauca',              capacity: 20, current: 16.2, threshold: 4.0, status: 'ok' },
      ],
    },
    {
      id: 'CS-002',
      name: 'Chapinero',
      city: 'Bogotá',
      address: 'Cl. 65 # 4 — 09',
      altitude: 2620,
      manager: 'Tomás Restrepo',
      status: 'warning',
      lastSync: 'hace 38 s',
      sacks: [
        { id: 'S-004', product: 'Andina Origen — Espresso Blend',  origin: 'Huila + Antioquia',  capacity: 20, current: 7.4,  threshold: 5.0, status: 'warning' },
        { id: 'S-005', product: 'Huila Single Origin',             origin: 'San Agustín, Huila', capacity: 20, current: 5.6,  threshold: 5.0, status: 'warning' },
        { id: 'S-006', product: 'Sierra Nevada Light Roast',       origin: 'Magdalena',          capacity: 50, current: 32.0, threshold: 12.0, status: 'ok' },
      ],
    },
    {
      id: 'CS-003',
      name: 'Usaquén',
      city: 'Bogotá',
      address: 'Cra. 6 # 119 — 24',
      altitude: 2580,
      manager: 'Isabela Quintero',
      status: 'ok',
      lastSync: 'hace 7 s',
      sacks: [
        { id: 'S-007', product: 'Andina Origen — Espresso Blend',  origin: 'Huila + Antioquia',  capacity: 20, current: 17.9, threshold: 5.0, status: 'ok' },
        { id: 'S-008', product: 'Cauca Decaf — Swiss Water',       origin: 'Cauca',              capacity: 20, current: 12.4, threshold: 4.0, status: 'ok' },
        { id: 'S-009', product: 'Sierra Nevada Light Roast',       origin: 'Magdalena',          capacity: 50, current: 41.8, threshold: 12.0, status: 'ok' },
        { id: 'S-010', product: 'Casa Espresso Profundo',          origin: 'Tolima',             capacity: 20, current: 15.1, threshold: 5.0, status: 'ok' },
      ],
    },
    {
      id: 'CS-004',
      name: 'El Poblado',
      city: 'Medellín',
      address: 'Cra. 33 # 7 — 151',
      altitude: 1495,
      manager: 'Diego Cárdenas',
      status: 'critical',
      lastSync: 'hace 5 s',
      sacks: [
        { id: 'S-011', product: 'Antioquia Origen — Concordia',    origin: 'Concordia',          capacity: 20, current: 3.2,  threshold: 5.0, status: 'critical' },
        { id: 'S-012', product: 'Andina Origen — Espresso Blend',  origin: 'Huila + Antioquia',  capacity: 20, current: 9.6,  threshold: 5.0, status: 'ok' },
        { id: 'S-013', product: 'Cauca Decaf — Swiss Water',       origin: 'Cauca',              capacity: 20, current: 13.0, threshold: 4.0, status: 'ok' },
      ],
    },
    {
      id: 'CS-005',
      name: 'San Antonio',
      city: 'Cali',
      address: 'Cra. 10 # 1 — 32',
      altitude: 1018,
      manager: 'Mariana Velasco',
      status: 'critical',
      lastSync: 'hace 19 s',
      sacks: [
        { id: 'S-014', product: 'Valle Profundo — Sevilla',        origin: 'Sevilla, Valle',     capacity: 20, current: 4.1,  threshold: 5.0, status: 'critical' },
        { id: 'S-015', product: 'Sierra Nevada Light Roast',       origin: 'Magdalena',          capacity: 50, current: 8.5,  threshold: 12.0, status: 'critical' },
        { id: 'S-016', product: 'Casa Espresso Profundo',          origin: 'Tolima',             capacity: 20, current: 10.2, threshold: 5.0, status: 'ok' },
        { id: 'S-017', product: 'Cauca Decaf — Swiss Water',       origin: 'Cauca',              capacity: 20, current: 14.7, threshold: 4.0, status: 'ok' },
        { id: 'S-018', product: 'Andina Origen — Espresso Blend',  origin: 'Huila + Antioquia',  capacity: 20, current: 11.9, threshold: 5.0, status: 'ok' },
      ],
    },
  ],

  recentEvents: [
    { time: '14:47:03', store: 'Centro',     type: 'telemetry', message: 'Saco S-001 actualizó peso a 14.62 kg', severity: 'info' },
    { time: '14:46:48', store: 'El Poblado', type: 'order',     message: 'Saco S-011 cruzó umbral · orden #2189 generada',   severity: 'critical' },
    { time: '14:46:32', store: 'San Antonio', type: 'security', message: 'Paquete con firma HMAC inválida rechazado',         severity: 'security' },
    { time: '14:46:12', store: 'Usaquén',    type: 'telemetry', message: 'Saco S-009 actualizó peso a 41.82 kg', severity: 'info' },
    { time: '14:45:56', store: 'Chapinero',  type: 'order',     message: 'Saco S-005 cruzó umbral · orden #2188 generada',   severity: 'warning' },
    { time: '14:45:30', store: 'Centro',     type: 'telemetry', message: 'Saco S-003 actualizó peso a 16.24 kg', severity: 'info' },
    { time: '14:44:58', store: 'San Antonio', type: 'order',    message: 'Saco S-015 cruzó umbral · orden #2187 generada',   severity: 'critical' },
    { time: '14:44:22', store: 'Medellín',   type: 'telemetry', message: 'Saco S-013 actualizó peso a 13.04 kg', severity: 'info' },
  ],

  recentOrders: [
    { id: '#2189', store: 'El Poblado',   product: 'Antioquia Origen — Concordia',    quantity: '20 kg', status: 'procesando', createdAt: '14:46:48' },
    { id: '#2188', store: 'Chapinero',    product: 'Huila Single Origin',             quantity: '20 kg', status: 'confirmada', createdAt: '14:45:56' },
    { id: '#2187', store: 'San Antonio',  product: 'Sierra Nevada Light Roast',       quantity: '50 kg', status: 'procesando', createdAt: '14:44:58' },
    { id: '#2186', store: 'Chapinero',    product: 'Andina Origen — Espresso Blend',  quantity: '20 kg', status: 'enviada',    createdAt: '12:14:02' },
  ],
};

// Export for module scripts
export default MOCK_DATA;
