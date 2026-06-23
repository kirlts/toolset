# Toolset Personal Hermes Sandbox — extends default Hermes image with tools
FROM python:3.11-slim

# Install git and CA certificates for gh CLI
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        git \
        ca-certificates \
        curl \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
