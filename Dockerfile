FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata
COPY pyproject.toml ./

# Install Python dependencies directly with pip
RUN pip install --no-cache-dir \
    aiogram==3.13.1 \
    httpx==0.27.0 \
    pydantic==2.9.2 \
    python-dotenv==1.0.1

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run the bot
CMD ["python", "main.py"]

