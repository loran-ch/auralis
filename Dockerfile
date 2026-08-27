FROM python:3.12-slim

# 视频抽帧/裁剪、百度 ASR 音频转换及中英文板书 OCR。
# 默认使用 Debian/PyPI 官方源；企业内网可在构建时传入自己的镜像地址。
# APT 重试用于吸收上游索引的短暂网络错误，镜像源持续故障时仍会明确失败。
ARG APT_MIRROR=deb.debian.org
ARG PYPI_INDEX_URL=https://pypi.org/simple
RUN set -eux; \
    if [ "${APT_MIRROR}" != "deb.debian.org" ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi; \
    for attempt in 1 2 3; do \
        if apt-get -o Acquire::Retries=3 update; then break; fi; \
        if [ "${attempt}" = 3 ]; then exit 1; fi; \
        sleep "${attempt}"; \
    done; \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/003.UI/backend

COPY 003.UI/backend/requirements.txt .
RUN pip install --no-cache-dir --index-url "${PYPI_INDEX_URL}" -r requirements.txt

COPY 003.UI/backend/ .
COPY 003.UI/frontend/ /app/003.UI/frontend/
COPY website/ /app/website/

ENV ENVIRONMENT=production
ENV HOST=0.0.0.0
ENV PORT=8010

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "2"]
