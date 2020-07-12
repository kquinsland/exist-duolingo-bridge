# Bare bones, for now
##

##
# borrowed from: https://eugene-babichenko.github.io/blog/2019/09/28/nightly-versions-makefiles/
##
# Vars about build state
AG_COMMIT := $(shell git rev-list --abbrev-commit --tags --max-count=1)
TAG := $(shell git describe --abbrev=0 --tags ${TAG_COMMIT} 2>/dev/null || true)
COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(TAG:v%=%)

ifneq ($(COMMIT), $(TAG_COMMIT))
	VERSION := $(VERSION)-next-$(COMMIT)-$(DATE)
endif

# Indicate if build done w/ uncommitted files
ifneq ($(shell git status --porcelain),)
	VERSION := $(VERSION)-dirty
endif

FLAGS := "VERSION_STRING=$(VERSION)"

build:
	docker build --build-arg $(FLAGS) -t duo2exist.io .

dkr-clean:
	docker image rm duo2exist.io

run: 
	docker run  -v ${CURDIR}/config:/duo-to-exist.io/config:ro --rm -it duo2exist.io
