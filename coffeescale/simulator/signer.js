// =============================================================
// CoffeeScale Simulator — Firma HMAC-SHA256
// Driver de Seguridad (E3): Integridad de Origen
// =============================================================

import { createHmac } from "node:crypto";

/**
 * Genera la firma HMAC-SHA256 de un payload.
 *
 * @param {object} payload — el objeto JSON a firmar.
 * @param {string} secret — la clave compartida con el servidor.
 * @returns {string} firma en hexadecimal.
 *
 * Diseño: se firma el JSON canonicalizado (claves ordenadas) para
 * evitar discrepancias por orden de propiedades entre simulador y
 * el lado del verificador (Lambda securityValidator).
 */
export function signPayload(payload, secret) {
  const canonical = canonicalJson(payload);
  return createHmac("sha256", secret).update(canonical).digest("hex");
}

/**
 * Genera el header de autorización completo.
 * Formato: "HMAC-SHA256 keyId=<deviceId>, signature=<hex>"
 *
 * Este formato es decodificable por la Lambda securityValidator
 * que documenta el ADR-003 (Hexagonal).
 */
export function buildAuthHeader(deviceId, signature) {
  return `HMAC-SHA256 keyId=${deviceId}, signature=${signature}`;
}

/**
 * Serializa un objeto JSON con claves ordenadas alfabéticamente.
 * Garantiza que el mismo payload produzca siempre el mismo string.
 */
function canonicalJson(obj) {
  if (obj === null || typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj))                       return "[" + obj.map(canonicalJson).join(",") + "]";

  const keys = Object.keys(obj).sort();
  const pairs = keys.map((k) => JSON.stringify(k) + ":" + canonicalJson(obj[k]));
  return "{" + pairs.join(",") + "}";
}
