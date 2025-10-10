FROM python:3.14-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ioping \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/disk-monitor.py .
COPY app/requirements.txt .
RUN chmod 755 ./disk-monitor.py

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Run as root since we need device access
# In production, consider using --cap-add=SYS_ADMIN or mounting /dev with appropriate permissions
USER root

EXPOSE 8000

CMD ["python", "disk-monitor.py"]
