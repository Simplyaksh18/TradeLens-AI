# TradeLens frontend — Vite production build served by Nginx.
#
# Build context is frontend/ (see compose.yaml).

FROM node:22-slim AS build
WORKDIR /app

# Dependencies first so they're cached across source-only rebuilds.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes these in at build time (VITE_* vars are public, compiled into
# the JS bundle — never secrets; see .env.example). Defaults keep the
# browser-visible origin identical to native `npm run dev` (localhost:5173)
# so no Google OAuth "Authorized JavaScript origins" change is needed.
ARG VITE_API_BASE_URL=http://localhost:5173
ARG VITE_GOOGLE_CLIENT_ID=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_GOOGLE_CLIENT_ID=${VITE_GOOGLE_CLIENT_ID}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Uses 127.0.0.1, not "localhost": this image's /etc/hosts resolves
# "localhost" to ::1 (IPv6) before 127.0.0.1, but nginx's `listen 80;`
# only binds the IPv4 wildcard -- so `wget http://localhost/` reliably
# connection-refused here even though nginx is healthy and reachable via
# the container's real IPv4 address (confirmed via `docker exec` during
# Phase 3F Docker acceptance). This is a healthcheck-command fix only --
# no application behavior changed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

EXPOSE 80
