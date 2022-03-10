FROM alpine:latest

ENV HOST=localhost

ENV CONFIG=/config/config.json

RUN apk add \
        python3-dev \
        musl-dev \
        make \
        openssl-dev \
        libffi-dev \
	py3-pip \
	ffmpeg \
        gcc

RUN pip3 install \
	flask \
	requests \
	retrying \
	pyjwt \
	bcrypt

# Copy files
COPY /app.py /app/app.py
COPY /stb.py /app/stb.py
COPY /templates /app/templates
COPY /static /app/static

ENTRYPOINT ["python3","-u","/app/app.py"]
