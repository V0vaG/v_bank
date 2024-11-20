FROM python:3.9-slim

ARG VERSION
ENV B_NUM=$VERSION

WORKDIR ~/

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD gunicorn --bind 0.0.0.0:5000 wsgi:app
