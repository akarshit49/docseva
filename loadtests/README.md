# DocSeva Load + Smoke Tests

These are the load and smoke tests called out in
`EXECUTION_PLAN_MULTI_CHANNEL.md` §19 (Testing Strategy). They run on
[k6](https://k6.io) so they can be triggered locally or from CI without any
Python dependencies.

## Install

```bash
brew install k6     # macOS
# or
sudo apt install k6 # Debian/Ubuntu
```

## Run the smoke test (deploy gate)

```bash
K6_BASE_URL=https://docseva.in k6 run loadtests/smoke.js
```

Pass criteria: 100% success on `/health` and `/whatsapp/health` within 1s.
CI runs this after every deploy; a non-zero exit blocks the rollout.

## Run the sister-quote load test

```bash
K6_API_URL=https://api.docseva.in \
K6_BOT_TOKEN=$API_BOT_TOKEN       \
K6_TG_USER_ID=999000001            \
k6 run loadtests/sister_quote.js
```

Pass criteria (also defined as thresholds in the script):
- p(95) of `/process/sister_quote` (preview mode) under **8s**
- error rate under **2%**
- health probes p(95) under **300ms**

The default workload ramps to 20 concurrent VUs over 1 minute and holds for 4
minutes. That mirrors a busy morning sales spike (~4 RPS sustained), well
above our v1 audience of ~20 dealers.

## CI integration

Add to your deploy pipeline:

```yaml
- name: Smoke test
  run: k6 run --quiet loadtests/smoke.js
  env:
    K6_BASE_URL: ${{ secrets.PROD_URL }}
```

For nightly load testing, schedule `sister_quote.js` against the staging
environment (never prod — we don't want to chew through real users' quota).
