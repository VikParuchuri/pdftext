FROM python:3.12.3-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk update && apk add python3-dev \
                          gcc \
                          musl-dev
                          

WORKDIR /app

COPY extract_text.py  /app/
COPY pdftext /app/
COPY models /app/
COPY scripts  /app/
COPY requirements.txt /app/
                                                   
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

CMD [ "python3", "extract_text.py" ] 