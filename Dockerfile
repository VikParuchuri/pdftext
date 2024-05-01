FROM python:3.12.3-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache \
    build-base \
    python3-dev \
    py3-pip \
    lapack-dev \
    gfortran \
    libffi-dev

WORKDIR /app

COPY .  /app/
COPY pyproject.toml  /app/
                                                   
RUN pip install poetry
RUN poetry install --no-root

CMD [ "python3", "extract_text.py" ] 