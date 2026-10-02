# ----------------------------------------------------
# Stage 1: Build the React + Vite + Three.js Frontend
# ----------------------------------------------------
FROM node:20-slim AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ----------------------------------------------------
# Stage 2: Python + PyTorch + FastAPI Backend Server
# ----------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=7860 \
    FRONTEND_DIST=/srv/frontend/dist

WORKDIR /srv

# Install CPU-only torch first for fast builds and small image footprint
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /build/dist /srv/frontend/dist

# Copy backend app
COPY backend/app ./app

EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
