FROM ghcr.io/osgeo/gdal:ubuntu-full-3.8.0

# Install Python, pip, and spatialite
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    libspatialite7 \
    libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

# Set Python as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

WORKDIR /app

# Copy requirements first for better caching
COPY requirements-test.txt .
COPY setup.py .
COPY setup.cfg .
COPY pyproject.toml .
COPY MANIFEST.in .
COPY README.rst .
COPY openwisp_firmware_upgrader ./openwisp_firmware_upgrader
COPY openwisp_modem_upgrader ./openwisp_modem_upgrader

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-test.txt
RUN pip install --no-cache-dir -e .

# Copy the rest of the application
COPY . .

WORKDIR /app/tests

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver_plus 0.0.0.0:8000 --cert-file cert.pem --key-file key.pem"]
