FROM python:${DOCKER_TAG}

WORKDIR /app

# Minimal dependencies
RUN pip install --no-cache-dir boto3 requests tenacity

COPY app/updater.py .

CMD ["python", "updater.py"]
