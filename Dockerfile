FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY visualizer/requirements.txt .

# Install dependencies without cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy the visualizer application
COPY visualizer/ .

# Expose port (Railway provides PORT env var)
EXPOSE 8000

# Run the application with PORT from environment (defaults to 8000).
# Clip export (/api/clip) renders + VP9-encodes a ~30s WebM synchronously, which
# takes well over gunicorn's default 30s worker timeout. Bump the timeout and run
# a second worker so the rest of the site stays responsive during a render.
CMD ["/bin/sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 300 --graceful-timeout 300"]
