#!/bin/bash

# Docker wrapper script for WSL when Docker Desktop integration is not enabled
# This script forwards docker commands to docker.exe on the Windows side

docker.exe "$@"