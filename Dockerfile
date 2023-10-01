##########
# BASE
##########
FROM alpine:latest AS base

ENV HOST=localhost
ENV CONFIG=/config/config.json

# Install required system packages
RUN apk add \
	ffmpeg \
	py3-pip \
	tzdata

# Install pip requirements
RUN pip3 install \
	flask \
	requests \
	waitress

# Copy app files
COPY /app.py /app/app.py
COPY /stb.py /app/stb.py
COPY /templates /app/templates
COPY /static /app/static

WORKDIR /app

##########
# DEBUG
##########
FROM base AS debug

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
#RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
#USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "app.py"]

##########
# RELEASE
##########
FROM base AS release

ENTRYPOINT ["python3","-u","app.py"]
