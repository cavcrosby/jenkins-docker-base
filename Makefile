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

# targets
GET_VIRTUALENV_PYTHON_VERSION = get-virtualenv-python-version

# include other generic makefiles
include docker.mk
export CONTAINER_NAME = jenkins-base
export CONTAINER_NETWORK = jbc1
export CONTAINER_VOLUME = jenkins_home:/var/jenkins_home
export DOCKER_REPO = cavcrosby/jenkins-base
DOCKER_VCS_LABEL = tech.cavcrosby.jenkins.base.vcs-repo=https://github.com/cavcrosby/jenkins-docker-base

include python.mk
# overrides defaults set by included makefiles
VIRTUALENV_PYTHON_VERSION = 3.9.5

include ansible.mk
ANSISRC = $(shell find . \
	\( \
		\( -type f \) \
		-and \( -name '*.yml' \) \
	\) \
	-and ! \( -name '.python-version' \) \
	-and ! \( -path '*.git*' \) \
)

# simply expanded variables
executables := \
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
>	@echo '  ${TEST}         - runs test suite for the project'
>	@echo '  ${CLEAN}        - removes files generated from all targets'
>	@echo 'Common make configurations (e.g. make [config]=1 [targets]):'
>	@echo '  ANSIBLE_JBC_LOG_SECRETS      - toggle logging secrets from Ansible when deploying a'
>	@echo '                                 project image (e.g. false/true, or 0/1)'
>	@echo '  CONTINUOUS_INTEGRATION       - toggle to possibly differentiate target behavior'
>	@echo '                                 during ci (e.g. false/true, or 0/1)'

.PHONY: ${SETUP}
${SETUP}: ${DOCKER_ANSIBLE_INVENTORY} ${PYENV_POETRY_SETUP}
>	${ANSIBLE_GALAXY} collection install --requirements-file ./requirements.yml

.PHONY: ${IMAGE}
${IMAGE}: ${DOCKER_IMAGE}

.PHONY: ${DEPLOY}
${DEPLOY}: ${DOCKER_TEST_DEPLOY}

.PHONY: ${DISMANTLE}
${DISMANTLE}: ${DOCKER_TEST_DEPLOY_DISMANTLE}

.PHONY: ${GET_VIRTUALENV_PYTHON_VERSION}
${GET_VIRTUALENV_PYTHON_VERSION}:
>	@echo ${VIRTUALENV_PYTHON_VERSION}

.PHONY: ${TEST}
${TEST}:
>	${PYTHON} -m unittest --verbose

.PHONY: ${CLEAN}
${CLEAN}: ${DOCKER_IMAGE_CLEAN}
