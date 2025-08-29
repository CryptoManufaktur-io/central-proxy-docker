ARG DOCKER_TAG=3.12-slim
FROM python:${DOCKER_TAG}

WORKDIR /app

RUN apt-get update && apt-get install -y ioping && apt-get clean

COPY app/disk-monitor.py /app/disk-monitor.py

# Install Prometheus client library
RUN pip install --no-cache-dir  prometheus_client

EXPOSE 8000

CMD ["python3", "disk-monitor.py"]
