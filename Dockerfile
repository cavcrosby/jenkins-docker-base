FROM jenkins/jenkins:lts@sha256:c878e1aac1f5152a6234b33a10542c7f694b7c5c37de27191d1c173800853b93

ARG BRANCH
ARG COMMIT
LABEL tech.cavcrosby.jenkins.base.branch="${BRANCH}"
LABEL tech.cavcrosby.jenkins.base.commit="${COMMIT}"
LABEL tech.cavcrosby.jenkins.base.vcs-repo="https://github.com/cavcrosby/jenkins-docker-base"

# parent jenkins image already has JENKINS_HOME defined
ENV CASC_JENKINS_CONFIG_FILE "casc.yaml"
ENV PLUGINS_FILE "plugins.txt"
ENV JENKINS_UC_DOWNLOAD_URL "https://ftp-chi.osuosl.org/pub/jenkins/plugins"
ENV JAVA_OPTS "-Djenkins.install.runSetupWizard=false -Dmail.smtp.starttls.enable=true"

# this variable is picked up by the plugin, do not change to '*_PATH'
ENV CASC_JENKINS_CONFIG "${JENKINS_HOME}/${CASC_JENKINS_CONFIG_FILE}"
ENV PLUGINS_FILE_PATH "/usr/share/jenkins/ref/${PLUGINS_FILE}"

COPY "${PLUGINS_FILE}" "${PLUGINS_FILE_PATH}"
RUN jenkins-plugin-cli --plugin-file "${PLUGINS_FILE_PATH}"
COPY "${CASC_JENKINS_CONFIG_FILE}" "${CASC_JENKINS_CONFIG}"
