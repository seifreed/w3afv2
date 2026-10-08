# w3af.org
# https://github.com/andresriancho/w3af/tree/master/extras

FROM python:3.14-slim
LABEL maintainer="Andres Riancho <andres.riancho@gmail.com>"

# Initial setup
RUN mkdir /home/w3af
WORKDIR /home/w3af
ENV HOME /home/w3af
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LOGNAME w3af
# Squash errors about "Falling back to ..." during package installation
ENV TERM linux
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Update before installing any package
RUN apt-get update -y
RUN apt-get upgrade -y
RUN apt-get dist-upgrade -y

# Install basic system requirements.
RUN apt-get install -y --no-install-recommends build-essential libxslt1-dev libxml2-dev \
                       libsqlite3-dev libyaml-dev openssh-server git wget xdot \
                       ca-certificates libffi-dev zlib1g-dev nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Add the w3af user
# TODO - actually use the w3af user instead of running everything as root
RUN useradd w3af

# Get ssh package ready
RUN mkdir /var/run/sshd
RUN echo 'root:w3af' | chpasswd
RUN mkdir /home/w3af/.ssh/
RUN echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDjXxcHjyVkwHT+dSYwS3vxhQxZAit6uZAFhuzA/dQ2vFu6jmPk1ewMGIYVO5D7xV3fo7/RXeCARzqHl6drw18gaxDoBG3ERI6LxVspIQYjDt5Vsqd1Lv++Jzyp/wkXDdAdioLTJyOerw7SOmznxqDj1QMPCQni4yhrE+pYH4XKxNx5SwxZTPgQWnQS7dasY23bv55OPgztI6KJzZidMEzzJVKBXHy1Ru/jjhmWBghiXYU5RBDLDYyT8gAoWedYgzVDmMZelLR6Y6ggNLOtMGiGYfPWDUz9Z6iDAUsOQBtCJy8Sj8RwSQNpmOgSzBanqnhed14hLwdYhnKWcPNMry71 w3af@w3af-docker.org' > /home/w3af/.ssh/w3af-docker.pub
RUN mkdir -p /root/.ssh/
RUN cat /home/w3af/.ssh/w3af-docker.pub >> /root/.ssh/authorized_keys

COPY requirements.txt /tmp/w3af-requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /tmp/w3af-requirements.txt

# Install w3af
ADD . /home/w3af/w3af
WORKDIR /home/w3af/w3af
RUN ./w3af_console ; true

# Change the install script to add the -y and not require input
RUN sed 's/sudo //g' -i /tmp/w3af_dependency_install.sh
RUN sed 's/apt-get/apt-get -y/g' -i /tmp/w3af_dependency_install.sh
RUN sed 's/pip install/pip install --upgrade/g' -i /tmp/w3af_dependency_install.sh

# Run the dependency installer
RUN /tmp/w3af_dependency_install.sh

# Run the dependency installer
RUN ./w3af_gui ; true
RUN sed 's/sudo //g' -i /tmp/w3af_dependency_install.sh
RUN sed 's/apt-get/apt-get -y/g' -i /tmp/w3af_dependency_install.sh
RUN sed 's/pip install/pip install --upgrade/g' -i /tmp/w3af_dependency_install.sh
RUN /tmp/w3af_dependency_install.sh

# Compile the py files into pyc in order to speed-up w3af's start
RUN python -m compileall -q .

# Cleanup to make the image smaller
RUN rm /tmp/w3af_dependency_install.sh
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*
RUN rm -rf /tmp/pip-build-root

EXPOSE 22 44444

CMD ["/usr/sbin/sshd", "-D"]
