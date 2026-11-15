# syntax=docker/dockerfile:1

FROM python:3.11-slim

# aiortc / pylibsrtp / PyAV ship manylinux wheels with their native libraries
# statically linked, so no system libs (libsrtp2, ffmpeg) are required here.
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Bind 0.0.0.0 so the container is reachable from the frontend service.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
