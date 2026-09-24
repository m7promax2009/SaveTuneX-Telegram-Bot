FROM python:3.12-slim

# Install system dependencies: FFmpeg is required for audio/video conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and database
COPY . .

# Expose Render / Cloud port
EXPOSE 10000

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

CMD ["python", "bot.py"]
