FROM jenkins/jenkins:lts@sha256:3dec77ef6636c4f4068f855fb2857bd3e8942b12bdd9c7429bd64ab8bc392527

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
