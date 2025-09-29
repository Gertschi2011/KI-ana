#!/usr/bin/env node
/**
 * Example: Device SSE client (Node.js)
 *
 * Requirements:
 *   npm install eventsource
 *
 * Usage:
 *   export KI_HOST="https://ki-ana.at"
 *   export DEVICE_ID=123
 *   export DEVICE_TOKEN="<token>"
 *   node examples/device_client_node.js
 */
const EventSource = require('eventsource');

const HOST = process.env.KI_HOST || 'http://127.0.0.1:8000';
const DEVICE_ID = process.env.DEVICE_ID || '0';
const TOKEN = process.env.DEVICE_TOKEN || '';

if (!TOKEN || !DEVICE_ID || DEVICE_ID === '0'){
  console.error('Please set DEVICE_ID and DEVICE_TOKEN env vars.');
  process.exit(2);
}

const url = `${HOST}/api/os/devices/${DEVICE_ID}/events`;
const headers = { 'Authorization': `Bearer ${TOKEN}` };

console.log('Connecting SSE:', url);
const es = new EventSource(url, { headers });

es.onopen = () => console.log('[sse] open');
es.onerror = (e) => console.error('[sse] error', e && e.message);
es.onmessage = (e) => {
  // Each event data is JSON: { id, ts, type, payload }
  console.log('[event]', e.data);
};
