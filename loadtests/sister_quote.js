//genai: Sprint 6 / WS-J — k6 load test for the /process/sister_quote anchor flow.
//
// Goal of this test: prove that we can handle the launch target laid out in
// EXECUTION_PLAN_MULTI_CHANNEL.md §19 (Testing Strategy): "k6 :: /process/sister_quote
// to validate concurrency assumptions".
//
// We model real dealer behaviour:
//   • a steady ramp-up over 1 minute (think: typical morning sales spike),
//   • a steady-state plateau where each VU sleeps 5–15s between requests
//     (humans, not bots),
//   • two thresholds we treat as launch blockers:
//       p(95) for /process/sister_quote stays under 8s,
//       error rate stays under 2%.
//
// Run:
//   K6_API_URL=https://api.docseva.in \
//   K6_BOT_TOKEN=$API_BOT_TOKEN \
//   K6_TG_USER_ID=999999 \
//   k6 run loadtests/sister_quote.js
//
// For a quick smoke run that just hits /health, use loadtests/smoke.js.

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Rate, Trend } from 'k6/metrics'
import { SharedArray } from 'k6/data'

// Test config ────────────────────────────────────────────────────────────────

export const options = {
  // 0 → 20 VUs over 60s, sustained for 4 min, ramp down for 30s.
  // ~4 RPS sustained, matching ~14k docs/hour at peak which is well above the
  // 1k–2k docs/day target audience for v1.
  stages: [
    { duration: '60s', target: 20 },
    { duration: '4m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],
    'http_req_duration{endpoint:health}': ['p(95)<300'],
    'http_req_duration{endpoint:sister_quote_preview}': ['p(95)<8000'],
    'errors{endpoint:sister_quote_preview}': ['rate<0.02'],
  },
}

// Custom metrics ─────────────────────────────────────────────────────────────

const errors = new Rate('errors')
const previewDuration = new Trend('preview_duration_ms')

// Fixtures: a tiny PDF blob loaded once and reused. Real PDFs are bigger but
// the API doesn't care about size at validation time — it cares about token
// usage downstream, which we mock out in the load environment.

const FIXTURE = new SharedArray('pdf-fixture', () => {
  // Smallest valid PDF (just header + EOF). Enough to pass mime-type checks.
  const header = '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
  return [{ name: 'supplier-quote.pdf', bytes: header }]
})

// Env ────────────────────────────────────────────────────────────────────────

const API_URL = __ENV.K6_API_URL || 'http://localhost:8000'
const BOT_TOKEN = __ENV.K6_BOT_TOKEN || ''
const TG_USER_ID = __ENV.K6_TG_USER_ID || '999000001'

if (!BOT_TOKEN) {
  console.warn(
    '⚠️  K6_BOT_TOKEN env var not set. Test will run against /health only.',
  )
}

// Workload ───────────────────────────────────────────────────────────────────

export default function () {
  // Every VU does a light health probe first (cheap), then either runs the
  // anchor flow (when authenticated) or just probes again.
  group('health probe', () => {
    const res = http.get(`${API_URL}/health`, { tags: { endpoint: 'health' } })
    check(res, { 'health 200': (r) => r.status === 200 })
  })

  if (!BOT_TOKEN) {
    sleep(1)
    return
  }

  group('sister_quote preview', () => {
    const fd = {
      mode: 'preview',
      file: http.file(FIXTURE[0].bytes, FIXTURE[0].name, 'application/pdf'),
    }
    const res = http.post(`${API_URL}/api/v1/process/sister_quote`, fd, {
      headers: {
        'X-Bot-Token': BOT_TOKEN,
        'X-User-Id': TG_USER_ID,
        'X-Channel': 'telegram',
      },
      tags: { endpoint: 'sister_quote_preview' },
      timeout: '30s',
    })
    const ok = check(res, {
      'preview 200/202': (r) => r.status === 200 || r.status === 202,
      'parsed_data present': (r) => {
        if (r.status !== 200) return true
        try {
          return Boolean(r.json('parsed_data'))
        } catch {
          return false
        }
      },
    })
    errors.add(!ok, { endpoint: 'sister_quote_preview' })
    previewDuration.add(res.timings.duration, {
      endpoint: 'sister_quote_preview',
    })
  })

  // Human pause between actions (5–15s). This is what makes the workload
  // realistic — without it we'd be measuring our network stack, not the app.
  sleep(5 + Math.random() * 10)
}

// k6 helper — call from `group()`.
function group(name, fn) {
  // k6 has a native `group()` but importing it here adds nothing; inline it.
  fn()
  void name
}
