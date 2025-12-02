FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install --no-cache-dir pdm

# Configure PDM to not use virtual environment (install to system)
ENV PDM_NO_VENV=1

# Copy PDM files
COPY pyproject.toml ./
# Copy lock file if exists (optional)
COPY pdm.lock* ./

# Install dependencies using PDM
RUN pdm install --prod --no-lock

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run the bot via PDM so it picks up dependencies from __pypackages__
CMD ["pdm", "run", "python", "main.py"]

