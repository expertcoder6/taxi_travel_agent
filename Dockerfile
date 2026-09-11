# ============================================================
# Stage 1: Build Next.js Frontend
# ============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
ENV BACKEND_URL=http://127.0.0.1:8000
RUN npm run build

# ============================================================
# Stage 2: Runtime image with Python & Node.js
# ============================================================
FROM python:3.11-slim
WORKDIR /app

# Install Node.js runtime for Next.js server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build & node_modules
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder /app/frontend/package*.json ./frontend/
COPY --from=frontend-builder /app/frontend/next.config.mjs ./frontend/
COPY --from=frontend-builder /app/frontend/node_modules ./frontend/node_modules

# Copy startup script
COPY start.sh ./
RUN chmod +x start.sh

ENV PORT=3000
EXPOSE 3000

CMD ["./start.sh"]
