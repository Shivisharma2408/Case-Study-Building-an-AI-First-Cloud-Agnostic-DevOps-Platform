# syntax=docker/dockerfile:1.7
# ---- build stage ----
FROM node:22.12.0-alpine3.21 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run lint && npm run build

# ---- runtime stage: unprivileged nginx (uid 101, listens on 8080) ----
FROM nginxinc/nginx-unprivileged:1.27.3-alpine3.20 AS runtime
# Upstream the SPA proxies /api to. Ingress routes /api directly in Kubernetes;
# this proxy keeps docker-compose (and a bare `kubectl port-forward`) working.
ENV BACKEND_UPSTREAM=http://backend:8000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/nginx-health || exit 1
