# syntax=docker/dockerfile:1
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Sistem paketleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    ca-certificates curl \
    iputils-ping dnsutils netcat-traditional \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PEP 668: sistem Python yerine izole bir venv kullan
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Python paketleri (wheel tercihli)
RUN pip install --upgrade pip setuptools wheel
RUN pip install --prefer-binary ldap3==2.9.1
RUN pip install --prefer-binary requests-ntlm==1.2.0
RUN pip install --prefer-binary ntlm-auth
RUN pip install --prefer-binary xmltodict==0.13.0 pywinrm==0.4.3
RUN pip install --prefer-binary tqdm==4.66.4 ping3==4.0.8
RUN pip install --prefer-binary pandas==2.2.2

# Hızlı kontrol (opsiyonel)
RUN python -c "import ldap3, winrm, pandas, requests_ntlm, tqdm, ping3, xmltodict; print('All good')"

# Uygulama dosyaları
COPY ./script/query.py /app/query.py

# Varsayılan komut yok; docker-compose 'command:' ile çalıştıracak
