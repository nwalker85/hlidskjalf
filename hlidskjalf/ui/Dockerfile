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
RUN npm run build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 odin

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=odin:nodejs /app/.next/standalone ./
COPY --from=builder --chown=odin:nodejs /app/.next/static ./.next/static

USER odin

EXPOSE 3900

ENV PORT=3900
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]

