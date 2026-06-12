# Standalone AoE2 Replay Viewer.
# Build context = the REPO ROOT (the app imports the aoe2x package):
#   docker build -f apps/viewer/Dockerfile .
# On Railway: railway.json sets dockerfilePath; root directory stays the repo.
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY apps/viewer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The aoe2x library (blueprint, classifier, SPA assets) + this app
COPY pyproject.toml ./
COPY aoe2x/ ./aoe2x/
RUN pip install --no-cache-dir --no-deps -e .
COPY apps/viewer/server.py ./server.py

EXPOSE 8000

CMD ["/bin/sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 300"]
