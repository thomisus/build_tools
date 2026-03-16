FROM ubuntu:24.04

ENV TZ=Etc/UTC
ENV DEBIAN_FRONTEND=noninteractive

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN echo 'keyboard-configuration keyboard-configuration/layoutcode string us' | debconf-set-selections && \
    echo 'keyboard-configuration keyboard-configuration/modelcode string pc105' | debconf-set-selections

RUN apt-get -y update && \
    apt-get -y install sudo \
                       git \
                       git-lfs \
                       curl \
                       wget \
                       p7zip-full

ADD . /build_tools
WORKDIR /build_tools

# Install local Python
RUN cd tools/linux && \
    ./python.sh

# Fetch Qt binaries
RUN cd tools/linux && \
    ./python3/bin/python3 ./qt_binary_fetch.py amd64

# Install system dependencies
RUN cd tools/linux && \
    ./python3/bin/python3 ./deps.py

# Install CMake
RUN cd tools/linux && \
    ./cmake.sh

# Fetch sysroot
RUN cd tools/linux/sysroot && \
    ../python3/bin/python3 ./fetch.py amd64

ARG BRANCH=master
ENV BRANCH=${BRANCH}

CMD ["sh", "-c", "./tools/linux/python3/bin/python3 ./configure.py --sysroot \"1\" --clean \"0\" --update-light \"1\" --branch \"${BRANCH}\" --update \"1\" --module \"desktop server builder\" --qt-dir \"$(pwd)/tools/linux/qt_build/Qt-5.9.9\" && ./tools/linux/python3/bin/python3 ./make.py"]