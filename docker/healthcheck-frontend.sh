#!/bin/sh
wget -qO /dev/null http://localhost:8080/nginx-health || exit 1
