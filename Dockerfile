FROM kbase/sdkbase2:python
MAINTAINER KBase Developer [Dylan Chivian (DCChivian@lbl.gov)]
# -----------------------------------------

# Insert apt-get instructions here to install
# any required dependencies for your module.

RUN apt-get update -y
RUN apt-get install -y wget g++
RUN python --version
RUN pip install --upgrade pip
RUN pip --version

# IDBA needs psutil
RUN pip install psutil


# Install idba
RUN cd /opt \
    && wget https://github.com/loneknightpy/idba/releases/download/1.1.3/idba-1.1.3.tar.gz \
    && tar xvfz idba-1.1.3.tar.gz \
    && rm idba-1.1.3.tar.gz \
    && cd idba-1.1.3 \
    && sed -i -- 's/kMaxShortSequence *= *[0-9][0-9]*/kMaxShortSequence = 512/' src/sequence/short_sequence.h \
    && ./configure \
    && make

ENV PATH $PATH:/opt/idba-1.1.3/bin

# -----------------------------------------

COPY ./ /kb/module
RUN mkdir -p /kb/module/work
RUN chmod -R a+rw /kb/module

WORKDIR /kb/module

RUN make

ENTRYPOINT [ "./scripts/entrypoint.sh" ]

CMD [ ]
