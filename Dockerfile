FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for pandas/ssl
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# App deps
COPY pyproject.toml README.md ./
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install fastapi "uvicorn[standard]" pandas requests yfinance python-dateutil \
                gspread google-auth google-auth-httplib2

# App code
COPY app ./app

# Default port (platforms will override)
ENV PORT=8080
EXPOSE 8080

# Start
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]
