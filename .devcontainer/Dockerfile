# ==============================================================================
# CIS 531/731: Minimal DevContainer Dockerfile (MP2)
# ==============================================================================
# Base image pinned for stability
ARG BASE_IMAGE=pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

# Pull conditionally based on the passed argument
FROM ${BASE_IMAGE}

# 1. Install System Dependencies (Java for PySpark, FFmpeg for Whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    openjdk-17-jre-headless \
    ffmpeg \
    git \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 2. Configure Environment Variables
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PYSPARK_PYTHON=python3
ENV PIP_NO_CACHE_DIR=1

# 3. Install Python Dependencies (Strict Pinned Versions per MP2 Manifest)
RUN pip install --upgrade pip "setuptools<70.0.0" wheel && \
    pip install \
    pyspark==3.5.1 \
    torch==2.2.1 \
    transformers==4.38.2 \
    mlflow==2.11.1 \
    faiss-cpu==1.8.0 &&\
    pip install --no-build-isolation openai-whisper==20231117

# 4. Create Non-Root User (Required for standard DevContainer permissions)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME -s /bin/bash \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME
WORKDIR /workspace
