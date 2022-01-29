include base.mk

# recursive variables
ANSIBLE_INVENTORY_PATH = ./localhost

# docker related variables
export CONTAINER_NAME = jenkins-base
export CONTAINER_NETWORK = jbc1
export CONTAINER_VOLUME = jenkins_home:/var/jenkins_home
DOCKER_REPO = cavcrosby/jenkins-base
DOCKER_CONTEXT_TAG = latest
DOCKER_LATEST_VERSION_TAG = $(shell ${GIT} describe --tags --abbrev=0)

# targets
IMAGE = image
DEPLOY = deploy
DISMANTLE = dismantle

# to be passed in at make runtime
IMAGE_RELEASE_BUILD =

ifdef IMAGE_RELEASE_BUILD
	DOCKER_BUILD_OPTS = \
		--tag \
		${DOCKER_REPO}:${DOCKER_CONTEXT_TAG} \
		--tag \
		${DOCKER_REPO}:${DOCKER_LATEST_VERSION_TAG}
else
	DOCKER_CONTEXT_TAG = test
	DOCKER_BUILD_OPTS = \
		--tag \
		${DOCKER_REPO}:${DOCKER_CONTEXT_TAG}
endif
export DOCKER_CONTEXT_TAG

define ANSIBLE_INVENTORY =
cat << _EOF_
all:
  hosts:
    localhost:
      email_secret:
_EOF_
endef
export ANSIBLE_INVENTORY

# include other generic makefiles
include python.mk
# overrides defaults set by included makefiles
VIRTUALENV_PYTHON_VERSION = 3.9.5

include ansible.mk
ANSISRC = $(shell find . \
	\( \
		\( -type f \) \
		-or \( -name '*.yml' \) \
	\) \
	-and ! \( -name '.python-version' \) \
	-and ! \( -path '*.git*' \) \
)

# executables
DOCKER = docker
GAWK = gawk
GIT = git
executables = \
	${DOCKER}\
	${GIT}

# simply expanded variables
_check_executables := $(foreach exec,${executables},$(if $(shell command -v ${exec}),pass,$(error "No ${exec} in PATH")))

.PHONY: ${HELP}
${HELP}:
	# inspired by the makefiles of the Linux kernel and Mercurial
>	@echo 'Common make targets:'
>	@echo '  ${SETUP}        - installs the distro-independent dependencies for this'
>	@echo '                 project'
>	@echo '  ${IMAGE}        - creates the base docker image that host Jenkins'
>	@echo '  ${DEPLOY}       - creates a container from the project image'
>	@echo '  ${DISMANTLE}    - removes a deployed container and the supporting'
>	@echo '                 environment setup'
>	@echo '  ${CLEAN}        - removes files generated from all targets'

.PHONY: ${SETUP}
${SETUP}: ${PYENV_POETRY_SETUP}
>	eval "$${ANSIBLE_INVENTORY}" > "${ANSIBLE_INVENTORY_PATH}"

.PHONY: ${IMAGE}
${IMAGE}:
>	${DOCKER} build \
		--build-arg BRANCH="$$(git branch --show-current)" \
		--build-arg COMMIT="$$(git show --format=%h --no-patch)" \
		${DOCKER_BUILD_OPTS} \
		.

.PHONY: ${DEPLOY}
${DEPLOY}:
>	 ${ANSIBLE_PLAYBOOK} --inventory ./localhost ./create-container.yml --ask-become-pass

.PHONY: ${DISMANTLE}
${DISMANTLE}:
>	${DOCKER} rm --force "${CONTAINER_NAME}"
>	${DOCKER} network rm "${CONTAINER_NETWORK}"
>	${DOCKER} volume rm --force "$$(echo "${CONTAINER_VOLUME}" \
		| ${GAWK} --field-separator ':' '{print $$1}')"

.PHONY: ${CLEAN}
${CLEAN}:
>	${DOCKER} rmi ${DOCKER_REPO}:test $$(${DOCKER} images \
		--filter label="tech.cavcrosby.jenkins.base.vcs-repo=https://github.com/cavcrosby/jenkins-docker-base" \
		--filter dangling="true" \
		--format "{{.ID}}")
