# Hub-VM-Image Backend-MVP (T-0032; E5). Ein Container, kein Zustand (SWR-024).
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pyyaml
WORKDIR /repos
EXPOSE 8080
CMD ["python", "platform/backend/server.py", "--repos", "/repos", "--host", "0.0.0.0", "--port", "8080"]
