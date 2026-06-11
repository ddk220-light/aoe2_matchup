FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies without cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port (Railway provides PORT env var)
EXPOSE 8000

# Run the application with PORT from environment (defaults to 8000)
CMD ["/bin/sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT:-8000}"]
