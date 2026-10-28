FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scripts ./scripts
COPY docs ./docs
CMD ["python", "scripts/import_documents.py"]
