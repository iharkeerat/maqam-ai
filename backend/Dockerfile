# Optional container pathway. Python CI verifies source/tests, not this image build.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY research/ research/
COPY engine/ engine/
COPY models/ models/
COPY reports/ reports/
RUN mkdir -p outputs
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
