# ---------- Base ----------
FROM python:3.12-slim

# Install OS deps needed for psycopg2 & Pillow (if you use images)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev musl-dev \
        && rm -rf /var/lib/apt/lists/*

# Create a non‑root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appgroup && \
    useradd -u ${UID} -g ${GID} -m appuser

WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project (except files ignored by .dockerignore)
COPY . .

# Switch to non‑root user
USER appuser

# Collect static files at container start (optional – you can run manually)
# ENTRYPOINT ["sh", "-c", "python manage.py collectstatic --noinput && exec \"$@\"", "--"]
# The above line is commented out; you can uncomment if you want the container
# to run `collectstatic` automatically on start.

# Default command (overridden in compose) – keep it lightweight
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]