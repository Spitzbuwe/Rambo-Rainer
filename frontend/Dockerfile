# syntax=docker/dockerfile:1
# Dev-Server (Vite): --host 0.0.0.0 / --port 5173 überschreiben die feste 127.0.0.1:3000
# in vite.config.js ohne diese Datei zu ändern.
FROM node:22-alpine

RUN apk add --no-cache curl

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --prefer-offline --no-audit

COPY . .

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
  && chown node:node /docker-entrypoint.sh \
  && chown -R node:node /app

USER node

EXPOSE 5173

ENV NODE_ENV=development

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=60s \
  CMD curl -fsS http://127.0.0.1:5173/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
