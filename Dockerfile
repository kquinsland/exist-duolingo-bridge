##
# See: https://hub.docker.com/_/python?tab=tags
FROM python:3.8.1-alpine

##
# Arguments that should get passed to build-tool:
# $ docker build <...> --build-arg GIT_COMMIT=$(git log -1 --format=%h) --build-arg GIT_BRANCH=$( git symbolic-ref HEAD --short ) .
ARG GIT_BRANCH="NotDefined"
ARG GIT_COMMIT="NotDefined"

# Make space for script
RUN mkdir /duo-to-exist
WORKDIR /duo-to-exist

# Copy over requirements, install them
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the code + config
COPY config.ini .
COPY main.py .

# Apply labels
LABEL git.branch=${GIT_BRANCH}
LABEL git.commit=${GIT_COMMIT}

LABEL "author"="Karl Quinsland"
LABEL "details"="https://github.com/kquinsland/exist-duolingo-bridge/"
LABEL description="Dullingo to Exist.io sync tool"

##
# We set the entrypoint to be the main.py which will still allow for users to pass in additional arguments on the
#   command line or via CMD
ENTRYPOINT [ "python", "./main.py" ]