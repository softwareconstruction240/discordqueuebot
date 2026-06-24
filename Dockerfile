FROM python:3.14.3-slim AS compile

COPY ./src/resources/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.14.3-slim AS build

WORKDIR /bot

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg && rm -rf /var/lib/apt/lists/*

COPY --from=compile /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links /wheels /wheels/*.whl
COPY ./src .

CMD ["python", "bot.py"]
