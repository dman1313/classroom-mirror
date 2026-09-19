FROM ubuntu:24.04

# Classroom Mirror pins the Python 3.11 toolchain (README "Retained stack
# direction"). Ubuntu 24.04 ships Python 3.12, so install 3.11 from deadsnakes.
# libgl1 + libglib2.0-0 are the OpenCV runtime libraries needed on headless
# Linux. Keep this layer to stable system dependencies only; repository
# dependencies (venvs, pip packages, the pose model) live in install.sh.
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-dev \
        python3.11-venv \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ubuntu:24.04 ships a default non-root "ubuntu" user (uid 1000); the agent
# checks out and runs the repository as that user.
USER ubuntu
