FROM python:3.12-slim AS wheels
WORKDIR /
RUN apt update && \
  apt install -y --no-install-recommends  build-essential
COPY requirements.txt /requirements.txt
RUN pip3 wheel --no-cache-dir --wheel-dir /wheels -r /requirements.txt

FROM python:3.12.0-slim
RUN adduser --home /app --uid 1000 docker
WORKDIR /app
COPY --from=wheels /wheels ./wheels
RUN pip3 install --no-cache-dir wheels/*.whl
RUN rm -rf ./wheels
USER 1000:1000
COPY --chown=1000:1000 . .
ENTRYPOINT ["python3", "cm_assistant.py"]
