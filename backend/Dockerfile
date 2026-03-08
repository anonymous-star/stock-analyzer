FROM python:3.11-slim

WORKDIR /app

# lightgbm, pandas 빌드에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# pandas-ta가 numba를 끌어오는데 빌드 실패하므로,
# 1) pandas-ta를 의존성 없이 먼저 설치
# 2) 나머지 패키지 설치 (pandas-ta는 이미 있으므로 skip)
RUN pip install --no-cache-dir --no-deps pandas-ta && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
