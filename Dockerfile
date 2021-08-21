FROM alpine:latest

ENV HOST=localhost

ENV CONFIG=/config/config.json

RUN apk add \
	py3-pip

RUN pip3 install \
	fastapi \
	requests \
	uvicorn \
	jinja2 \
	python-multipart

# Copy files
COPY /app.py /app/app.py
COPY /templates /app/templates

ENTRYPOINT ["python3","-u","/app/app.py"]
