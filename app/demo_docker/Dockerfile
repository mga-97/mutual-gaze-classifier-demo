FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies given in documentation in superbuild
# https://github.com/robotology/robotology-superbuild#linux
RUN mkdir -p /etc/bash_completion.d/ &&\
    apt-get update &&\
    apt-get install -y \
        # MISC
        bash-completion \
        qtbase5-dev \
        qt5-qmake \
        qt5-qmake \
        cmake \
        cmake-curses-gui \ 
        build-essential \
        vim \
        terminator \
        wget \
        git \
        #core
        coinor-libipopt-dev \ 
        libboost-system-dev \
        libboost-filesystem-dev \
        libboost-thread-dev \
        libopencv-dev \
        libode-dev \
        liblua5.1-dev \
        lua5.1 \ 
        libsdl1.2-dev \
        libxml2-dev \
        # YARP
        libace-dev \
        libeigen3-dev \
        libgsl0-dev \
        libedit-dev \
        libqcustomplot-dev \
        qtmultimedia5-dev \
        qtdeclarative5-dev \
        libqt5opengl5-dev \
        qttools5-dev \
        libtinyxml-dev \
        #yarp-gui
        qtbase5-dev \
        qtdeclarative5-dev \
        qtmultimedia5-dev \
        qml-module-qtquick2 \
        qml-module-qtquick-window2 \
        qml-module-qtmultimedia \
        qml-module-qtquick-dialogs \
        qml-module-qtquick-controls \
        qml-module-qt-labs-folderlistmodel \
        qml-module-qt-labs-settings 

# CMake 3.20.0 and add repository if ubuntu < 18.04
RUN wget https://github.com/Kitware/CMake/releases/download/v3.20.0/cmake-3.20.0-linux-x86_64.tar.gz \
    && tar -xzvf cmake-3.20.0-linux-x86_64.tar.gz \
    && ln -sf $(pwd)/cmake-3.20.0-linux-x86_64/bin/* /usr/bin/



#Some definitions
ARG PROJECTS_DIR=/projects
ARG CMAKE_GENERATOR="Unix Makefiles"
ARG BUILD_TYPE=Release
ARG CMAKE_EXTRA_OPTIONS=-j2
ARG INSTALL_DIR="/usr/local"
ARG release="master -b master_branch"
ARG sbtag="Stable"


RUN echo "DEBUG ==>  Release:" ${release} &&\
    echo "DEBUG ==>  TAG: " ${tag}


# Setup entrypoint
ARG ROBOTOLOGY_INITIALIZATION_FILE=/usr/local/bin/setup_robotology_tdd.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY setup.sh ${ROBOTOLOGY_INITIALIZATION_FILE}
ENTRYPOINT [ "/usr/local/bin/entrypoint.sh" ]

RUN apt-get install -y python3.10-dev

RUN apt-get update && apt-get install -y \
        python3.10 \
        python3-pip

RUN apt-get update && apt-get install -y \
        python3.10-dev \
        python3.10-venv \
        python3.10-distutils 

RUN python3 -m venv /venv
    
ENV PATH=/venv/bin:$PATH

RUN mkdir ${PROJECTS_DIR} && cd ${PROJECTS_DIR} &&\
    git clone https://github.com/robotology/robotology-superbuild.git &&\
    cd robotology-superbuild &&\
    git checkout ${release} &&\
    ./scripts/install_apt_dependencies.sh &&\
    mkdir build && cd build &&\
    cmake .. \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
        -DNON_INTERACTIVE_BUILD:BOOL=ON \
        -DROBOTOLOGY_ENABLE_CORE:BOOL=ON \
        -DYCM_USE_DEPRECATED:BOOL=OFF \
        -DROBOTOLOGY_USES_GAZEBO=OFF \
        -DROBOTOLOGY_USES_PYTHON=ON \
        -DROBOTOLOGY_PROJECT_TAGS=${sbtag} \
        -DYCM_EP_INSTALL_DIR=${INSTALL_DIR} \
        &&\
    # Build all the projects
    cmake --build . --target update-all -- -j4 &&\
    cmake --build . -- ${CMAKE_EXTRA_OPTIONS}


# This step ensures python looks for yarp bindings in the correct place
RUN echo 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3/dist-packages' >> $ROBOTOLOGY_INITIALIZATION_FILE

RUN echo "source ${INSTALL_DIR}/share/robotology-superbuild/setup.sh" >> $ROBOTOLOGY_INITIALIZATION_FILE


# Waiting https://github.com/robotology/robotology-superbuild/issues/95
RUN echo 'export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${ROBOTOLOGY_SUPERBUILD_INSTALL_PREFIX}/lib/rtf'  >> $ROBOTOLOGY_INITIALIZATION_FILE

# The bashrc is read only when opening an interactive shell. Let other projects find packages contained in the superbuild.
ENV CMAKE_PREFIX_PATH=${INSTALL_DIR}

#add checkRobotInterface
RUN cd ${PROJECTS_DIR} &&\
    git clone https://github.com/icub-tech-iit/appsAway.git && \
    cd  appsAway/modules/checkRobotInterface && \
    mkdir build && cd build && \
    cmake .. \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
        &&\
    cmake --build . -- ${CMAKE_EXTRA_OPTIONS} && \
    cp ./checkRobotInterface /usr/local/bin

# apparently tf_slim is not installed by default, so we install it
RUN pip install tf_slim

#The EXPOSE instruction does not actually publish the port. 
#It functions as a type of documentation between the person who builds the image and the person who runs the container, about which ports are intended to be published. 
#To actually publish the port when running the container, use the -p flag on docker run to publish and map one or more ports, or the -P flag to publish all exposed ports and map them to high-order ports.
EXPOSE 10000/tcp 10000/udp

# Some QT-Apps don't show controls without this
ENV QT_X11_NO_MITSHM 1
ENV YARP_COLORED_OUTPUT 1


ARG metadata="none"

ENV img_metadata=${metadata}

RUN echo 'export img_metadata=${metadata}'  >> $ROBOTOLOGY_INITIALIZATION_FILE
RUN echo 'echo 'This images has release=$release and had been building with superbuild_tag=$sbtag. Metadata=$metadata ' '  >> $ROBOTOLOGY_INITIALIZATION_FILE

CMD ["bash"]


RUN apt-get update && apt-get install -y \
        software-properties-common
RUN apt-get install -y \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    zlib1g-dev

RUN apt-get update

#### Install python packages ####
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --upgrade setuptools numpy==1.26.4 opencv-contrib-python pandas wheel scikit-learn keras tensorflow pynput

#### Dependencies ####
RUN apt-get install -y libgoogle-glog-dev libboost-all-dev libhdf5-serial-dev libatlas-base-dev

#### Install python bindings ####
RUN git config --global user.name icub
RUN git config --global user.email icub@iit.it

#### Install swig ####
RUN apt-get install swig

#### Compile yarp ####
RUN cd /projects/robotology-superbuild/build && \
    cmake .. \
    -DROBOTOLOGY_USES_PYTHON=ON \
    &&\
    make -j12
RUN export PYTHONPATH=/projects/robotology-superbuild/build/src/YARP/lib/python3

# ### Install torch, necessary for mmpose
RUN python3 -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2

# Install mmpose dependencies
RUN pip install -U openmim \
    && mim install mmengine \
    && mim install "mmcv==2.0.0rc4" \
    && mim install "mmdet>=3.0.0"

# Install mmpose
RUN git clone https://github.com/open-mmlab/mmpose.git \
    && cd mmpose \
    && pip install -r requirements.txt \
    && pip install -v -e .

# Install mmdeploy and onnx runtime
RUN pip install mmdeploy \
    && pip install mmdeploy-runtime-gpu \
    && pip install onnxruntime-gpu \
    && wget https://github.com/microsoft/onnxruntime/releases/download/v1.15.1/onnxruntime-linux-x64-gpu-1.15.1.tgz \
    && tar -zxvf onnxruntime-linux-x64-gpu-1.15.1.tgz 

ENV ONNXRUNTIME_DIR=/onnxruntime-linux-x64-gpu-1.15.1

ENV CUDA_BIN_PATH=/usr/local/cuda

ENV LD_LIBRARY_PATH=${ONNXRUNTIME_DIR}/lib:/usr/lib/x86_64-linux-gnu/:/usr/local/cuda-11.7/compat/:$LD_LIBRARY_PATH

# MMdeploy sdk prerequisites
RUN git clone https://github.com/openppl-public/ppl.cv.git \
    && cd ppl.cv \
    && git checkout tags/v0.7.0 -b v0.7.0 \
    && ./build.sh cuda

ENV PPLCV_DIR=/ppl.cv

# Install mmdeploy sdk
RUN git clone -b main https://github.com/open-mmlab/mmdeploy.git --recursive --depth=1 \
    && cd \mmdeploy \
    && mkdir -p build && cd build \
    && cmake .. \
        -DMMDEPLOY_BUILD_SDK=ON \
        -DMMDEPLOY_BUILD_SDK_PYTHON_API=ON \
        -DMMDEPLOY_BUILD_EXAMPLES=ON \
        -DMMDEPLOY_TARGET_DEVICES=cuda \
        -DMMDEPLOY_TARGET_BACKENDS=ort \
        -Dpplcv_DIR=${PPLCV_DIR}/cuda-build/install/lib/cmake/ppl \
        -DONNXRUNTIME_DIR=${ONNXRUNTIME_DIR} \
        -DCUDNN_DIR=${CUDNN_DIR} \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
    && make -j8 && make install
ENV MMDEPLOY_DIR=/mmdeploy
ENV MMPOSE_DIR=/mmpose

# Install ffmpeg libraries for video grabber utils
RUN apt update && apt install -y ffmpeg \ 
libavcodec-dev libavdevice-dev \ 
libavformat-dev libavutil-dev


# Install c++ unit test framework
RUN git clone https://github.com/catchorg/Catch2.git \
    && cd Catch2 \
    && cmake -Bbuild -H. -DBUILD_TESTING=OFF \
    && cmake --build build/ --target install


# Install the application
RUN git clone https://github.com/robotology/human-sensing.git \
    && cd human-sensing/yarpRTMPose \
    && mkdir build && cd build \
    && cmake .. \
    && make install \ 
    && cd /mmdeploy \
    && /human-sensing/yarpRTMPose/app/scripts/deploy.sh

#### Clone repository installation ####
RUN cd / projects/ && \
    git clone -b rtm https://github.com/mga-97/mutual-gaze-classifier-demo.git && \
    cd mutual-gaze-classifier-demo && \
    mkdir build && cd build && \
    cmake .. && \
    make install

# RUN yarp namespace /cer04
RUN yarp conf 192.168.100.10 10000
