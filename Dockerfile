FROM python:3.11-slim

WORKDIR /app

# System dependencies (ffmpeg is required for merging streams, MP3 extraction, thumbnail embedding)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Deno and add it to PATH permanently
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"
RUN curl -fsSL https://deno.land/install.sh | sh

# Python dependencies (installed into the image, not at startup)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --upgrade --pre yt-dlp && \
    pip install -r requirements.txt

# Copy the rest of the bot code
COPY . .

CMD ["python", "main.py"]
