FROM python:3.11-slim

WORKDIR /app

# Install deps first for caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY . /app

# Cloud Run listens on $PORT
ENV PORT=8080

# Start FastAPI
CMD exec uvicorn medusa.webapp:app --host 0.0.0.0 --port $PORT
