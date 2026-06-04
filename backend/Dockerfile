FROM python:3.12-slim

WORKDIR /app

COPY backend/pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "jinja2>=3.1" \
    "python-multipart>=0.0.9" \
    "sqlalchemy>=2.0" \
    "qdrant-client>=1.12" \
    "openai>=1.55" \
    "argon2-cffi>=23.1" \
    "pypdf>=5.0" \
    "pillow>=10.0" \
    "python-docx>=1.1" \
    "oauth-codex>=0.1" \
    "pytest>=8.0" \
    "httpx>=0.27" \
    "pydantic-settings>=2.0" \
    "itsdangerous>=2.2"

COPY backend/app ./app
COPY scripts ./scripts

ENV PYTHONPATH=/app

EXPOSE 8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088", "--workers", "1"]
