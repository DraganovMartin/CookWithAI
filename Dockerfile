FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COVERAGE_FILE=/tmp/.coverage \
    PYTHONPATH=/code/src \
    PATH=/usr/local/lib/python3.14/site-packages/bin:$PATH \
    DATABASE_PATH=/data/cookwithai.db

WORKDIR /code

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

# Nothing is installed during the build: dependencies are copied from vendor/, which
# scripts/vendor_deps.py fills once. Being its own layer, it isn't copied again for code changes.
# It has to land in site-packages: from anywhere else, Streamlit assumes it's in development mode
# and watches every package for changes.
COPY vendor /usr/local/lib/python3.14/site-packages

COPY --chown=appuser:appuser pyproject.toml README.md ./
COPY --chown=appuser:appuser .streamlit ./.streamlit
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser tests ./tests

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Create the schema before the server starts, so db-admin always finds the tables.
CMD ["sh", "-c", "python -m cookwithai.db.database && exec streamlit run src/cookwithai/main.py --server.address=0.0.0.0 --server.port=8501"]
