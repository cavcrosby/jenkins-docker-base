FROM jenkins/jenkins:lts

ARG BRANCH
ARG COMMIT
LABEL tech.conneracrosby.jenkins.base.branch=${BRANCH}
LABEL tech.conneracrosby.jenkins.base.commit=${COMMIT}
LABEL tech.conneracrosby.jenkins.base.vcs-repo="https://github.com/reap2sow1/jenkins-docker-base"

# parent jenkins image already has JENKINS_HOME defined
ENV CASC_JENKINS_CONFIG ${JENKINS_HOME}/casc.yaml
ENV JAVA_OPTS -Djenkins.install.runSetupWizard=false

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN /usr/local/bin/install-plugins.sh < /usr/share/jenkins/ref/plugins.txt
COPY casc.yaml ${CASC_JENKINS_CONFIG}
