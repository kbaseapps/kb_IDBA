FROM kbase/kbase:sdkbase.latest
MAINTAINER KBase Developer
# -----------------------------------------

# Insert apt-get instructions here to install
# any required dependencies for your module.

# RUN apt-get update


RUN sudo apt-get install python-dev libffi-dev libssl-dev
RUN pip install cffi --upgrade
RUN pip install pyopenssl --upgrade
RUN pip install ndg-httpsclient --upgrade
RUN pip install pyasn1 --upgrade

RUN pip install requests --upgrade \
    && pip install 'requests[security]' --upgrade \
    && pip install ipython \
    && apt-get install nano \
    && pip install psutil \
    && pip install pyyaml

# Install idba
RUN cd /opt \
    && wget https://github.com/loneknightpy/idba/releases/download/1.1.3/idba-1.1.3.tar.gz \
    && tar xvfz idba-1.1.3.tar.gz \
    && rm idba-1.1.3.tar.gz \
    && cd idba-1.1.3 \
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
