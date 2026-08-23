FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

RUN useradd --create-home --uid 1000 workspace \
    && mkdir -p /workspace /tmp/matplotlib \
    && chown -R workspace:workspace /workspace /tmp/matplotlib

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER workspace
WORKDIR /workspace

CMD ["sleep", "infinity"]
