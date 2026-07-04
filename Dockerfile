FROM python:3.11-slim

WORKDIR /app

ARG BGUTIL_PROVIDER_VERSION=1.3.1

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

# Install the BgUtils POT provider server used by the yt-dlp plugin
RUN curl -fsSL -o /tmp/bgutil-ytdlp-pot-provider.zip \
        "https://github.com/Brainicism/bgutil-ytdlp-pot-provider/archive/refs/tags/${BGUTIL_PROVIDER_VERSION}.zip" && \
    unzip /tmp/bgutil-ytdlp-pot-provider.zip -d /opt && \
    mv "/opt/bgutil-ytdlp-pot-provider-${BGUTIL_PROVIDER_VERSION}" /opt/bgutil-ytdlp-pot-provider && \
    cd /opt/bgutil-ytdlp-pot-provider/server && \
    deno install --allow-scripts=npm:canvas --frozen && \
    rm /tmp/bgutil-ytdlp-pot-provider.zip

# Python dependencies (installed into the image, not at startup)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --upgrade --pre "yt-dlp[default]" && \
    pip install -r requirements.txt

# Copy the rest of the bot code
COPY . .
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
