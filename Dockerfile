##
# TODO: links to tags
FROM python:3.8-alpine

# TODO: set up tags!

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config.ini .
COPY main.py .



CMD [ "python", "./main.py" ]