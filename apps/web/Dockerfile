# syntax=docker/dockerfile:1.7
# QuotePulse GMC web (Next.js 15, standalone output). Bun installs and builds; the
# runtime is plain Node with only the traced server bundle.
#
#   docker build -t quotepulse-web \
#     --build-arg NEXT_PUBLIC_API_URL=https://quote.example.com/api/v1 \
#     --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_... apps/web
#   (behind a TLS-inspecting proxy add: --secret id=corp_ca,src=/path/to/ca.pem)
#
# NEXT_PUBLIC_* values are inlined at build time, so they are build args. Dev mock auth
# can never be enabled in this image (it requires NODE_ENV !== "production").

ARG BUN_IMAGE=oven/bun:1.3-alpine
ARG NODE_IMAGE=node:22-alpine

# --- dependencies -------------------------------------------------------------
FROM ${BUN_IMAGE} AS deps
WORKDIR /app
COPY package.json bun.lock ./
# Optional corporate/TLS-inspection CA (TRD §6): docker build --secret id=corp_ca,src=ca.pem
# Mounted for this step only; it never lands in an image layer.
RUN --mount=type=secret,id=corp_ca,required=false \
    if [ -s /run/secrets/corp_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/corp_ca; fi; \
    bun install --frozen-lockfile

# --- build --------------------------------------------------------------------
FROM ${BUN_IMAGE} AS build
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=""
ARG NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
ARG NEXT_PUBLIC_CLERK_SIGN_UP_URL=/invite/accept
ARG NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/dashboard
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY} \
    NEXT_PUBLIC_CLERK_SIGN_IN_URL=${NEXT_PUBLIC_CLERK_SIGN_IN_URL} \
    NEXT_PUBLIC_CLERK_SIGN_UP_URL=${NEXT_PUBLIC_CLERK_SIGN_UP_URL} \
    NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=${NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# next/font downloads the Geist fonts at build time from Turbopack's Rust side, which
# reads SSL_CERT_FILE rather than NODE_EXTRA_CA_CERTS (same optional CA as above).
RUN --mount=type=secret,id=corp_ca,required=false \
    if [ -s /run/secrets/corp_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/corp_ca > /tmp/ca-bundle.pem 2>/dev/null \
        || cp /run/secrets/corp_ca /tmp/ca-bundle.pem; \
      export NODE_EXTRA_CA_CERTS=/run/secrets/corp_ca SSL_CERT_FILE=/tmp/ca-bundle.pem; \
    fi; \
    bun run build && rm -f /tmp/ca-bundle.pem

# --- migrations (one-off job: drizzle-kit migrate, optional seed) -------------
FROM build AS migrator
ENV NODE_ENV=production
CMD ["bun", "run", "db:migrate"]

# --- runtime ------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/health >/dev/null || exit 1
CMD ["node", "server.js"]
