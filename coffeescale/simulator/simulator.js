#!/usr/bin/env node
// =============================================================
// CoffeeScale — Simulador de Básculas IoT (Node.js CLI)
//
// Cubre la restricción RN-4: "Las básculas físicas aún están en
// fabricación en China, por lo que se debe usar un simulador de
// software que emule los dispositivos IoT".
//
// Uso:
//   node simulator.js [opciones]
//
// Ver README.md para todas las opciones.
// =============================================================

import { signPayload, buildAuthHeader } from "./signer.js";

// ---------- ANSI colors ----------
const C = {
  reset:  "\x1b[0m",
  dim:    "\x1b[2m",
  bold:   "\x1b[1m",
  italic: "\x1b[3m",
  red:    "\x1b[31m",
  green:  "\x1b[32m",
  yellow: "\x1b[33m",
  blue:   "\x1b[34m",
  magenta:"\x1b[35m",
  cyan:   "\x1b[36m",
  gray:   "\x1b[90m",
  burdeos:"\x1b[38;2;107;31;31m",
  coffee: "\x1b[38;2;74;44;26m",
  crema:  "\x1b[38;2;232;213;183m",
};

// ---------- Configuración por defecto ----------
const DEFAULTS = {
  stores: 5,
  devicesPerStore: 3,
  rate: 60,
  duration: 600,
  endpoint: "https://api.coffeescale.local/telemetry",
  secret: process.env.HMAC_SECRET || "DEMO_HMAC_SECRET_CHANGE_ME",
  dryRun: false,
  verbose: false,
};

// ---------- Catálogo de productos para realismo ----------
const PRODUCTS = [
  { name: "Andina Origen — Espresso Blend",   capacityKg: 20 },
  { name: "Huila Single Origin",               capacityKg: 20 },
  { name: "Cauca Decaf — Swiss Water",         capacityKg: 20 },
  { name: "Sierra Nevada Light Roast",         capacityKg: 50 },
  { name: "Casa Espresso Profundo",            capacityKg: 20 },
  { name: "Antioquia Origen — Concordia",      capacityKg: 20 },
  { name: "Valle Profundo — Sevilla",          capacityKg: 20 },
];

const STORE_NAMES = [
  "Bogotá Centro", "Bogotá Chapinero", "Bogotá Usaquén",
  "Medellín El Poblado", "Cali San Antonio",
  "Cartagena Bocagrande", "Barranquilla Norte",
  "Bucaramanga Cabecera", "Pereira El Lago", "Manizales Cable",
];

// =============================================================
// Parsing de argumentos
// =============================================================
function parseArgs(argv) {
  const opts = { ...DEFAULTS };
  const args = argv.slice(2);

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    const next = () => args[++i];
    switch (a) {
      case "--stores":            opts.stores = parseInt(next(), 10); break;
      case "--devices-per-store": opts.devicesPerStore = parseInt(next(), 10); break;
      case "--rate":              opts.rate = parseInt(next(), 10); break;
      case "--duration":          opts.duration = parseInt(next(), 10); break;
      case "--endpoint":          opts.endpoint = next(); break;
      case "--secret":            opts.secret = next(); break;
      case "--dry-run":           opts.dryRun = true; break;
      case "--verbose": case "-v": opts.verbose = true; break;
      case "--help":   case "-h":  printHelp(); process.exit(0);
      default:
        console.error(`${C.red}Opción desconocida: ${a}${C.reset}`);
        printHelp();
        process.exit(1);
    }
  }
  return opts;
}

function printHelp() {
  console.log(`
${C.bold}${C.burdeos}CoffeeScale — Simulador de Básculas IoT${C.reset}

${C.dim}Uso:${C.reset}
  node simulator.js [opciones]

${C.dim}Opciones:${C.reset}
  --stores N              Número de sucursales a simular           (def: ${DEFAULTS.stores})
  --devices-per-store N   Básculas por sucursal                    (def: ${DEFAULTS.devicesPerStore})
  --rate N                Segundos entre transmisiones por báscula (def: ${DEFAULTS.rate})
  --duration N            Duración total en segundos               (def: ${DEFAULTS.duration})
  --endpoint URL          URL del API de ingesta                   (def: ${DEFAULTS.endpoint})
  --secret KEY            Secreto compartido HMAC-SHA256           (def: variable HMAC_SECRET)
  --dry-run               No envía HTTP, solo imprime los paquetes
  --verbose, -v           Imprime detalles de cada transmisión
  --help, -h              Esta ayuda

${C.dim}Ejemplos:${C.reset}
  # Demo local sin red (5 tiendas, 3 básculas c/u, durante 60 s, una tx cada 5 s):
  node simulator.js --dry-run --duration 60 --rate 5 --verbose

  # Stress test apuntando a 10.000 req/min (167 req/s):
  node simulator.js --stores 1000 --devices-per-store 10 --rate 60

  # Apuntar al API real desplegado:
  node simulator.js --endpoint https://api.coffeescale.com/telemetry
`);
}

// =============================================================
// Generador de básculas
// =============================================================
function createDevices(opts) {
  const devices = [];
  for (let s = 0; s < opts.stores; s++) {
    const storeId   = `CS-${String(s + 1).padStart(3, "0")}`;
    const storeName = STORE_NAMES[s % STORE_NAMES.length];
    for (let d = 0; d < opts.devicesPerStore; d++) {
      const product  = PRODUCTS[(s + d) % PRODUCTS.length];
      const deviceId = `${storeId}-D${String(d + 1).padStart(2, "0")}`;
      devices.push({
        deviceId,
        storeId,
        storeName,
        product:       product.name,
        capacityKg:    product.capacityKg,
        currentKg:     product.capacityKg * (0.4 + Math.random() * 0.6),
        thresholdKg:   product.capacityKg * 0.25,
        consumptionKg: 0.05 + Math.random() * 0.15,  // kg/s simulados
      });
    }
  }
  return devices;
}

// =============================================================
// Loop de transmisión por báscula
// =============================================================
async function transmit(device, opts, stats) {
  // Simular consumo (algunas básculas se "rellenan" al llegar a 0)
  const elapsedSec = opts.rate;
  device.currentKg -= device.consumptionKg * elapsedSec * (Math.random() * 0.4 + 0.8);
  if (device.currentKg < 0) {
    device.currentKg = device.capacityKg * 0.95; // simula reposición física
  }

  const payload = {
    deviceId:   device.deviceId,
    storeId:    device.storeId,
    product:    device.product,
    weightKg:   Number(device.currentKg.toFixed(3)),
    capacityKg: device.capacityKg,
    timestamp:  new Date().toISOString(),
    nonce:      Math.random().toString(36).slice(2, 12),
  };

  const signature  = signPayload(payload, opts.secret);
  const authHeader = buildAuthHeader(device.deviceId, signature);

  stats.attempted++;

  if (opts.dryRun) {
    if (opts.verbose) printPacket(payload, signature, "DRY-RUN");
    stats.success++;
    return;
  }

  try {
    const res = await fetch(opts.endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": authHeader,
      },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      stats.success++;
      if (opts.verbose) printPacket(payload, signature, `HTTP ${res.status}`);
    } else {
      stats.failed++;
      console.log(`\n${C.red}✗ ${device.deviceId} → HTTP ${res.status}${C.reset}`);
    }
  } catch (err) {
    stats.failed++;
    if (opts.verbose) console.log(`\n${C.red}✗ ${device.deviceId} → ${err.message}${C.reset}`);
  }
}

function printPacket(payload, signature, label) {
  const sigShort = signature.slice(0, 16);
  const weight = payload.weightKg.toFixed(2);
  console.log(
    `${C.gray}[${new Date().toLocaleTimeString()}]${C.reset} ` +
    `${C.coffee}●${C.reset} ${C.bold}${payload.deviceId}${C.reset} ` +
    `${C.italic}${C.dim}${payload.product}${C.reset} → ` +
    `${C.crema}${weight} / ${payload.capacityKg} kg${C.reset} ` +
    `${C.gray}· HMAC ${sigShort}… · ${label}${C.reset}`
  );
}

// =============================================================
// Reportería en vivo (una línea actualizada in-place)
// =============================================================
function startReporter(stats, opts, startTime) {
  return setInterval(() => {
    const elapsed = (Date.now() - startTime) / 1000;
    const rps = (stats.attempted / elapsed).toFixed(2);
    const rpm = (rps * 60).toFixed(0);
    process.stdout.write(
      `\r${C.gray}┃${C.reset} ${C.bold}${stats.attempted.toString().padStart(6)}${C.reset} envíos · ` +
      `${C.green}${stats.success}${C.reset} ok · ` +
      `${C.red}${stats.failed}${C.reset} fail · ` +
      `${C.cyan}${rps} req/s${C.reset} · ` +
      `${C.cyan}${rpm} req/min${C.reset} · ` +
      `${C.gray}t = ${elapsed.toFixed(0)}s${C.reset}    `
    );
  }, 1000);
}

// =============================================================
// Main
// =============================================================
async function main() {
  const opts = parseArgs(process.argv);

  // Banner
  console.log(`
${C.burdeos}${C.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C.reset}
${C.burdeos}${C.bold}  CoffeeScale — Simulador de Básculas IoT${C.reset}
${C.coffee}  Andina Roasters · Ingeniería de Software II${C.reset}
${C.burdeos}${C.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C.reset}

${C.dim}Configuración:${C.reset}
  Sucursales:        ${C.bold}${opts.stores}${C.reset}
  Básculas/sucursal: ${C.bold}${opts.devicesPerStore}${C.reset}
  Total básculas:    ${C.bold}${opts.stores * opts.devicesPerStore}${C.reset}
  Frecuencia:        cada ${C.bold}${opts.rate}${C.reset} segundos por báscula
  Throughput esp.:   ${C.bold}${((opts.stores * opts.devicesPerStore * 60) / opts.rate).toFixed(0)}${C.reset} req/min
  Duración total:    ${C.bold}${opts.duration}${C.reset} segundos
  Endpoint:          ${C.bold}${opts.endpoint}${C.reset}
  Modo:              ${opts.dryRun ? C.yellow + "DRY-RUN (sin enviar)" : C.green + "LIVE (HTTP real)"}${C.reset}
`);

  if (!opts.dryRun && opts.secret === DEFAULTS.secret) {
    console.log(`${C.yellow}⚠ Usando el secreto HMAC por defecto. En producción usa --secret o variable HMAC_SECRET.${C.reset}\n`);
  }

  const devices = createDevices(opts);
  const stats   = { attempted: 0, success: 0, failed: 0 };
  const start   = Date.now();
  const endAt   = start + opts.duration * 1000;

  console.log(`${C.dim}Iniciando ${devices.length} básculas...${C.reset}\n`);

  const reporter = startReporter(stats, opts, start);

  // Programar transmisión por báscula con offset aleatorio para no sincronizar
  const timers = devices.map((device) => {
    const offset = Math.random() * opts.rate * 1000;
    return setTimeout(function tick() {
      if (Date.now() >= endAt) return;
      transmit(device, opts, stats);
      setTimeout(tick, opts.rate * 1000);
    }, offset);
  });

  // Cierre limpio
  const shutdown = (signal) => {
    clearInterval(reporter);
    timers.forEach((t) => clearTimeout(t));
    const elapsed = (Date.now() - start) / 1000;
    console.log(`\n\n${C.burdeos}${C.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C.reset}`);
    console.log(`${C.bold}  Resumen final${signal ? ` (interrumpido: ${signal})` : ""}${C.reset}`);
    console.log(`${C.burdeos}${C.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C.reset}\n`);
    console.log(`  ${C.dim}Duración:${C.reset}        ${elapsed.toFixed(1)} s`);
    console.log(`  ${C.dim}Intentos:${C.reset}        ${stats.attempted}`);
    console.log(`  ${C.dim}Exitosos:${C.reset}        ${C.green}${stats.success}${C.reset}`);
    console.log(`  ${C.dim}Fallidos:${C.reset}        ${C.red}${stats.failed}${C.reset}`);
    console.log(`  ${C.dim}Throughput med.:${C.reset} ${(stats.attempted / elapsed).toFixed(2)} req/s · ${((stats.attempted / elapsed) * 60).toFixed(0)} req/min`);
    console.log(`  ${C.dim}Tasa de éxito:${C.reset}   ${stats.attempted > 0 ? ((stats.success / stats.attempted) * 100).toFixed(2) : "0"} %\n`);
    process.exit(0);
  };

  process.on("SIGINT",  () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  setTimeout(() => shutdown(null), opts.duration * 1000 + 500);
}

main().catch((err) => {
  console.error(`${C.red}Error fatal:${C.reset}`, err);
  process.exit(1);
});
