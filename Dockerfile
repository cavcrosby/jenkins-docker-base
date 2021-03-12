FROM jenkins/jenkins:lts

ENV JAVA_OPTS -Djenkins.install.runSetupWizard=false
ENV JENKINS_HOME /var/jenkins_home
ENV CASC_JENKINS_CONFIG ${JENKINS_HOME}/casc.yaml

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN /usr/local/bin/install-plugins.sh < /usr/share/jenkins/ref/plugins.txt
COPY casc.yaml ${JENKINS_HOME}/casc.yaml
