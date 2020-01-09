#!/bin/bash

# Check if config.ini exists
if [ -e config.ini ]; then
  echo "building..."
  docker build -t duo-to-exist --build-arg GIT_COMMIT="$(git log -1 --format=%h)" --build-arg GIT_BRANCH="$(git symbolic-ref HEAD --short)" .
else
  echo "Config.ini not found, create one using config.ini.sample as a guide"
  exit 1
fi

echo "Building complete. Run: docker run --rm -it duo-to-exist"
