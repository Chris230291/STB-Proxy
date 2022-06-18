FROM alpine:latest

ENV HOST=localhost

ENV CONFIG=/config/config.json

ENV CACHE=/cache/

RUN apk add \
	py3-pip \
	ffmpeg \
	tzdata

RUN pip3 install \
	flask \
	requests\
	retrying

# Copy files
COPY /app.py /app/app.py
COPY /stb.py /app/stb.py
COPY /templates /app/templates
COPY /static /app/static

ENTRYPOINT ["python3","-u","/app/app.py"]
