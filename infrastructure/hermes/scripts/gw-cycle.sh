#!/usr/bin/env bash
sleep 3
GW_SVC=hermes-gateway
sudo systemctl kill -s KILL $GW_SVC
sleep 2
sudo systemctl start $GW_SVC
