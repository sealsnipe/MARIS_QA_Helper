FROM python:3.12-slim

WORKDIR /app

# poppler-utils provides pdfimages (used by vision_ocr extract for original-quality
# embedded images without resampling). Optional at runtime (pypdf fallback always
# available); installed for the high-fidelity path in production containers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
# PyPI antwortet auf manchen Deploy-Hosts schleppend; mit dem pip-Default
# (15s Timeout, 5 Retries) reißt dann der Metadaten-Abruf einzelner Pakete ab
# und pip meldet irreführend "ResolutionImpossible" statt des Netzwerkfehlers.
ENV PIP_DEFAULT_TIMEOUT=60 \
    PIP_RETRIES=10
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
