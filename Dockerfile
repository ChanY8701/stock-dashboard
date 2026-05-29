# ============================================================
# Dockerfile
# ============================================================
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Streamlit 포트
EXPOSE 8501

# 기본 명령: 대시보드 실행
CMD ["streamlit", "run", "app.py",
     "--server.port=8501",
     "--server.address=0.0.0.0",
     "--server.headless=true",
     "--browser.gatherUsageStats=false"]
