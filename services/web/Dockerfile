# #genai: Sprint 3 / WS-F — Dockerfile for the Next.js web channel.
# Multi-stage to keep the runtime image small (next standalone output).
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# Lockfile is optional in this scaffold. `--legacy-peer-deps` mirrors the
# standard Next.js + ESLint guidance: eslint-config-next still lists peerDeps
# as eslint ^7 || ^8 while we may opt into newer minors, so npm v10's stricter
# resolver refuses without this flag. Once a lockfile is committed `npm ci`
# becomes deterministic and the flag is a no-op.
RUN if [ -f package-lock.json ]; then \
      npm ci --legacy-peer-deps; \
    else \
      npm install --legacy-peer-deps; \
    fi

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

# Non-root runtime user.
RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
