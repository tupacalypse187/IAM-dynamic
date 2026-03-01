#!/bin/sh
wget -qO /dev/null http://localhost:8000/health || exit 1
