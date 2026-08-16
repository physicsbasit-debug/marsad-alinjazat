FROM node:22-alpine AS frontend
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./
COPY src ./src
ARG VITE_API_BASE_URL=
ARG VITE_BASE_PATH=/
ARG VITE_PREVIEW_MODE=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
ENV VITE_PREVIEW_MODE=${VITE_PREVIEW_MODE}
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY scripts ./scripts
COPY --from=frontend /app/dist ./dist
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
