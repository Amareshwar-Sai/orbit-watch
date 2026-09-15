FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ORBITWATCH_DB=/app/var/orbitwatch.db
WORKDIR /app
RUN groupadd --gid 10001 orbitwatch && useradd --uid 10001 --gid 10001 --no-create-home orbitwatch \
    && mkdir /app/var && chown 10001:10001 /app/var
COPY --chown=10001:10001 orbitwatch /app/orbitwatch
COPY --chown=10001:10001 data /app/data
COPY --chown=10001:10001 config /app/config
COPY --chown=10001:10001 static /app/static
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8000,timeout=3); c.request('GET','/health'); assert c.getresponse().status==200"
CMD ["python", "-m", "orbitwatch", "serve", "--container"]
