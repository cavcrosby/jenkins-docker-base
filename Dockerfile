FROM jenkins/jenkins:lts

ARG BRANCH
ARG COMMIT
LABEL tech.conneracrosby.jenkins.base.branch="${BRANCH}"
LABEL tech.conneracrosby.jenkins.base.commit="${COMMIT}"
LABEL tech.conneracrosby.jenkins.base.vcs-repo="https://github.com/cavcrosby/jenkins-docker-base"

# parent jenkins image already has JENKINS_HOME defined
ENV CASC_JENKINS_CONFIG_FILENAME "casc.yaml"
# this variable is picked up by the plugin, do not change to '..._PATH'
ENV CASC_JENKINS_CONFIG "${JENKINS_HOME}/${CASC_JENKINS_CONFIG_FILENAME}"
ENV JAVA_OPTS -Djenkins.install.runSetupWizard=false

COPY plugins.txt "/usr/share/jenkins/ref/plugins.txt"
# TODO(cavcrosby): install-plugins.sh is supposedly outdated/deprecated, look into jenkins-plugin-cli
RUN "/usr/local/bin/install-plugins.sh" < "/usr/share/jenkins/ref/plugins.txt"
COPY "$CASC_JENKINS_CONFIG_FILENAME" "$CASC_JENKINS_CONFIG"
