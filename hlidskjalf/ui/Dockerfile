# ============================================================================
# Hliðskjálf UI - The View from Odin's Throne
# ============================================================================

FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source
COPY . .

# Build
ENV NEXT_TELEMETRY_DISABLED=1
    # Provide dummy secret for build-time (actual secret set at runtime)
    ENV NEXTAUTH_SECRET=build-time-secret-will-be-overridden
RUN npm run build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create ravenhelm user (UID/GID 1001 per workspace standards)
RUN addgroup --system --gid 1001 ravenhelm && \
    adduser --system --uid 1001 -G ravenhelm ravenhelm

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=ravenhelm:ravenhelm /app/.next/standalone ./
COPY --from=builder --chown=ravenhelm:ravenhelm /app/.next/static ./.next/static

USER ravenhelm

EXPOSE 3900

ENV PORT=3900
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]

