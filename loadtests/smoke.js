//genai: Sprint 6 — minimal smoke test. Use after every deploy.
//
//   k6 run loadtests/smoke.js
//
// Pass criteria: every probed endpoint responds 2xx within 1s. This is what
// CI runs as a deploy gate — anything red here blocks the rollout.

import http from 'k6/http'
import { check } from 'k6'

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
}

const BASE = __ENV.K6_BASE_URL || 'http://localhost:80'

export default function () {
  const probes = [
    { path: '/health', expect: 200 },
    // The WhatsApp adapter is reachable via the nginx proxy too.
    { path: '/whatsapp/health', expect: 200 },
  ]
  for (const p of probes) {
    const res = http.get(`${BASE}${p.path}`)
    check(res, {
      [`${p.path} status`]: (r) => r.status === p.expect,
    })
  }
}
