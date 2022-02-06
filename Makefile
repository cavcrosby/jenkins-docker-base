include base.mk

# recursive variables
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
include docker.mk
export CONTAINER_NAME = jenkins-base
export CONTAINER_NETWORK = jbc1
export CONTAINER_VOLUME = jenkins_home:/var/jenkins_home
DOCKER_REPO = cavcrosby/jenkins-base
DOCKER_VCS_LABEL = tech.cavcrosby.jenkins.base.vcs-repo=https://github.com/cavcrosby/jenkins-docker-base

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

# simply expanded variables
override executables := \
	${docker_executables}\
	${python_executables}

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
${SETUP}: ${DOCKER_ANSIBLE_INVENTORY} ${PYENV_POETRY_SETUP}

.PHONY: ${IMAGE}
${IMAGE}: ${DOCKER_IMAGE}

.PHONY: ${DEPLOY}
${DEPLOY}: ${DOCKER_TEST_DEPLOY}

.PHONY: ${DISMANTLE}
${DISMANTLE}: ${DOCKER_TEST_DEPLOY_DISMANTLE}

.PHONY: ${CLEAN}
${CLEAN}: ${DOCKER_IMAGE_CLEAN}
