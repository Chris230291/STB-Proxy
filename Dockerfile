FROM alpine:latest

ENV HOST=localhost

ENV CONFIG=/config/config.json

RUN apk add \
	py3-pip \
	ffmpeg

RUN pip3 install \
	fastapi \
	requests \
	uvicorn \
	jinja2 \
	python-multipart \
	aiofiles

# Copy files
COPY /app.py /app/app.py
COPY /templates /app/templates
COPY /static /app/static

ENTRYPOINT ["python3","-u","/app/app.py"]