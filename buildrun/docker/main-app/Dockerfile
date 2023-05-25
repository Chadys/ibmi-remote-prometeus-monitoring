FROM python:3.10-buster as base-image

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends\
 odbcinst=2.3.6-0.1  libodbc1=2.3.6-0.1 odbcinst1debian2=2.3.6-0.1\
 unixodbc=2.3.6-0.1  unixodbc-dev=2.3.6-0.1 &&\
 apt-get clean && rm -rf /var/lib/apt/lists/*  /usr/share/doc /usr/share/man

COPY ./buildrun/docker/main-app/drivers/IBMiAccess_v1r1_LinuxAP/x86_64/ibm-iaccess-DRIVER_VERSION.amd64.deb /tmp
RUN dpkg -i /tmp/ibm-iaccess-DRIVER_VERSION.amd64.deb

# hadolint ignore=DL3059
RUN pip install --no-cache-dir pip-tools==6.8.0

# -----

FROM base-image as deploy-image

# creates a system user (-r), with no password, no home directory set, and no shell
RUN groupadd -r default-group && useradd -r -s /bin/false -g default-group default-user

WORKDIR /code
RUN chown -R default-user:default-group /code
COPY --chown=default-user:default-group ./src /code/
COPY --chown=default-user:default-group ./buildrun/docker/main-app/requirements/prod-requirements.txt /code/requirements.txt
RUN pip-sync requirements.txt --pip-args '--no-cache-dir --no-deps'
USER default-user

# -----
FROM base-image as dev-image

# Enable ODBC tracing
#RUN echo "[ODBC]\n\
#Trace = yes\n\
#TraceFile = /tmp/odbctrace.log\
#" >> /etc/odbcinst.ini

WORKDIR /code
COPY ./buildrun/docker/main-app/requirements/dev-requirements.txt /code/requirements.txt
RUN pip-sync requirements.txt --pip-args '--no-cache-dir --no-deps'
