#!/usr/bin/env bash
sleep 3
SVC=hermes-gateway
sudo systemctl kill -s KILL $SVC 2>/dev/null
sleep 1
sudo systemctl start $SVC 2>/dev/null
