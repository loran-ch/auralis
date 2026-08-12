FROM python:3.12-slim

# ffmpeg — 百度 ASR 音频格式转换依赖
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/003.UI/backend

COPY 003.UI/backend/requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY 003.UI/backend/ .
COPY 003.UI/frontend/ /app/003.UI/frontend/
COPY website/ /app/website/

ENV ENVIRONMENT=production
ENV HOST=0.0.0.0
ENV PORT=8010

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "2"]
