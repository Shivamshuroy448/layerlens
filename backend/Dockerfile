FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /srv

# Install CPU-only torch first for small image & fast builds
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 7860
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
