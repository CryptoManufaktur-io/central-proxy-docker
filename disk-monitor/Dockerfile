ARG DOCKER_TAG=3.13-slim
FROM python:${DOCKER_TAG}

ARG USER=diskmonitor
ARG UID=11000

# See https://stackoverflow.com/a/55757473/12429735RUN
RUN adduser \
    --disabled-password \
    --gecos "" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    --home "/home/diskmonitor" \
    --no-create-home \
    "${USER}"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ioping \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create and set home directory as working directory
RUN mkdir -p /home/diskmonitor && chown ${USER}:${USER} /home/diskmonitor
WORKDIR /home/diskmonitor

COPY --chown=${USER}:${USER} app/disk-monitor.py .
COPY --chown=${USER}:${USER} app/requirements.txt .
RUN chmod 555 ./disk-monitor.py

RUN pip install --no-cache-dir --require-hashes -r requirements.txt

USER diskmonitor

EXPOSE 8000

CMD ["python", "disk-monitor.py"]
