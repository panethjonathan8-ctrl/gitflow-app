FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim AS runtime
# hadolint ignore=DL3013
RUN pip install --no-cache-dir setuptools
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY app.py database.py ./
RUN chown -R appuser:appgroup /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production
ENV PORT=5000
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
