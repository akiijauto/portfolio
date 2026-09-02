FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci
COPY src ./src
COPY test ./test
RUN npx tsc

FROM node:22-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
ENV PORT=8000 WORKERS=2 NODE_ENV=production
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["node", "dist/src/server.js"]
