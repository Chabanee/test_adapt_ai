FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    binutils \
    build-essential \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    p7zip-full \
    wget \
    && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements.txt .

# Installe GDAL en correspondant exactement à la version système (évite les erreurs de compilation)
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "gdal==$(gdal-config --version)"

COPY . .

RUN mkdir -p /app/data
