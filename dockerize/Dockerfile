FROM python:3.8-slim-buster

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt
COPY drydocks.py drydocks.py
COPY config.py config.py
COPY data/shape /app/data/shape
#CMD ["while :; do :; done & kill -STOP $! && wait $!"]
ENTRYPOINT ["tail", "-f", "/dev/null"]