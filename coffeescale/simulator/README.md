# CoffeeScale — Simulador de Básculas IoT

Simulador de básculas digitales para el sistema **CoffeeScale** de Andina Roasters. Emula los dispositivos IoT que enviarán telemetría a la nube con firma criptográfica HMAC-SHA256.

Cubre la restricción **RN-4** del proyecto: *"Las básculas físicas aún están en fabricación en China, por lo que se debe usar un simulador de software que emule los dispositivos IoT"*.

---

## Requisitos

- **Node.js ≥ 18** (usa `fetch` nativo y `node:crypto`).
- Sin dependencias externas (todo es Node estándar).

```bash
node --version  # debe mostrar v18.x.x o superior
```

---

## Instalación

```bash
cd simulator
npm install   # opcional: solo si quieres usar los scripts de package.json
```

(Aunque el simulador no tiene dependencias externas, `npm install` registra el proyecto y habilita `npm start`).

---

## Uso rápido

### Modo demo (sin red, salida verbose)

Útil para presentaciones y desarrollo sin necesidad de backend desplegado:

```bash
node simulator.js --dry-run --duration 60 --rate 5 --verbose
```

Esto simula 5 sucursales × 3 básculas = 15 básculas transmitiendo cada 5 segundos durante 60 segundos. No envía HTTP.

### Modo demo con backend desplegado

```bash
node simulator.js \
  --endpoint https://api.coffeescale.com/telemetry \
  --secret "$HMAC_SECRET" \
  --stores 5 \
  --devices-per-store 3 \
  --rate 60 \
  --duration 600
```

### Stress test — escenario E1 (10.000 req/min)

```bash
node simulator.js \
  --stores 1000 \
  --devices-per-store 10 \
  --rate 60 \
  --duration 600 \
  --endpoint https://api.coffeescale.com/telemetry \
  --secret "$HMAC_SECRET"
```

Esto da `1.000 × 10 × 60 / 60 = 10.000 req/min sostenidos` durante 10 minutos — exactamente el target del escenario E1 (Disponibilidad: Ingesta Masiva).

---

## Argumentos disponibles

| Argumento | Default | Descripción |
|---|---|---|
| `--stores N` | `5` | Número de sucursales a simular |
| `--devices-per-store N` | `3` | Básculas por sucursal |
| `--rate N` | `60` | Segundos entre transmisiones de una báscula |
| `--duration N` | `600` | Duración total del simulacro (segundos) |
| `--endpoint URL` | `https://api.coffeescale.local/telemetry` | URL del API de ingesta |
| `--secret KEY` | `$HMAC_SECRET` o `DEMO_HMAC_SECRET_CHANGE_ME` | Clave compartida para firmar |
| `--dry-run` | off | No envía HTTP, solo imprime |
| `--verbose`, `-v` | off | Imprime detalle de cada paquete |
| `--help`, `-h` | — | Ayuda |

---

## Formato del paquete enviado

Cada báscula envía un POST HTTP con este payload:

```json
{
  "deviceId":   "CS-001-D01",
  "storeId":    "CS-001",
  "product":    "Andina Origen — Espresso Blend",
  "weightKg":   14.623,
  "capacityKg": 20,
  "timestamp":  "2026-05-18T14:47:03.142Z",
  "nonce":      "k9x2p4q1m8"
}
```

Y este header de autenticación:

```
Authorization: HMAC-SHA256 keyId=CS-001-D01, signature=a1b2c3d4...64chars
```

El `securityValidator` del backend verifica la firma usando la misma clave compartida. Si la firma no coincide → el mensaje se rechaza y se registra en logs de auditoría (driver E3 — Integridad de Origen).

### Detalle del esquema de firma

1. Se serializa el payload como **JSON canonicalizado** (claves ordenadas alfabéticamente) — esto garantiza que el simulador y el verificador obtengan el mismo string a firmar.
2. Se aplica HMAC-SHA256 sobre el string canónico con la clave compartida.
3. La firma resultante se envía en hexadecimal en el header `Authorization`.

Ver `signer.js` para la implementación.

---

## Salida del simulador

Durante la ejecución verás algo así:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CoffeeScale — Simulador de Básculas IoT
  Andina Roasters · Ingeniería de Software II
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Configuración:
  Sucursales:        5
  Básculas/sucursal: 3
  Total básculas:    15
  Frecuencia:        cada 5 segundos por báscula
  Throughput esp.:   180 req/min
  Duración total:    60 segundos
  Endpoint:          https://api.coffeescale.local/telemetry
  Modo:              DRY-RUN (sin enviar)

Iniciando 15 básculas...

[14:47:03] ● CS-001-D01 Andina Origen — Espresso Blend → 14.62 / 20 kg · HMAC a1b2c3d4e5f6g7h8… · DRY-RUN
[14:47:04] ● CS-002-D02 Huila Single Origin → 11.81 / 20 kg · HMAC e1f2g3h4i5j6k7l8… · DRY-RUN
┃    142 envíos · 142 ok · 0 fail · 2.37 req/s · 142 req/min · t = 60s
```

Al terminar (o si haces `Ctrl+C`), imprime el resumen final con throughput medido y tasa de éxito.

---

## Trazabilidad con el proyecto

| Driver / Escenario | Cómo lo aborda el simulador |
|---|---|
| **E1 — Ingesta Masiva** | Permite escalar hasta 10.000 req/min con `--stores 1000 --devices-per-store 10` |
| **E3 — Integridad de Origen** | Firma HMAC-SHA256 con clave compartida en cada paquete |
| **RN-4 — Hardware en fabricación** | El simulador *es* el sustituto del hardware físico |
| **Driver Modificabilidad (E4)** | El generador de payload está aislado en `simulator.js`; agregar formato de un nuevo fabricante = crear un nuevo `transmit*()` |

---

## Limitaciones del MVP

- **No simula fallas de red.** Si quieres probar resiliencia, encadena con `tc` (Linux) o herramientas de chaos engineering.
- **No firma con claves por dispositivo distintas.** Todos usan la misma clave compartida. Para producción se debería derivar una clave por `deviceId`.
- **Modo `dry-run` no genera carga real**, solo imprime. Para validar el throughput real del API hay que ejecutarlo en modo LIVE.

---

## Licencia

MIT — Proyecto académico, Ingeniería de Software II, 2026.
