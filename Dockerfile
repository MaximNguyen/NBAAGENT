# Stage 1: Build React frontend
FROM node:20-slim AS frontend
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# Install system deps for lightgbm
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
COPY nba_betting_agent/ ./nba_betting_agent/
RUN pip install --no-cache-dir ".[api]"

# Copy built frontend from stage 1
COPY --from=frontend /app/dashboard/dist ./dashboard/dist

# Railway sets PORT env var
ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "nba_betting_agent.api.server"]
