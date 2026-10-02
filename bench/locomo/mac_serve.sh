#!/bin/bash
# Wait until the HaluMem chain on the shared Mac Studio has finished and :8090 is free,
# then start OUR llama_cpp server (same command line the chain used) and an ssh tunnel
# to it at 127.0.0.1:18090. Never touches processes it did not start.
#   bash mac_serve.sh wait-start     # blocks, then starts server + tunnel
#   bash mac_serve.sh stop           # stops the server and the tunnel we started
MAC=chrismarmo@100.126.162.38
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=30 $MAC"
PYV='~/jpwork/rg/.venv-judge/bin/python'
MODEL='~/jpwork/rg_private/models/qwen3-14b-a8cc1361.gguf'
case $1 in
wait-start)
  while true; do
    busy=$($SSH 'pgrep -f "[r]un_judged.sh" | wc -l; lsof -nP -iTCP:8090 -sTCP:LISTEN 2>/dev/null | grep -c LISTEN' 2>/dev/null | xargs)
    echo "$(date +%H:%M) chain-procs/listeners: $busy"
    [ "$busy" = "0 0" ] && break
    sleep 600
  done
  $SSH "cd ~/jpwork && mkdir -p locomo_run && nohup $PYV -m llama_cpp.server --model $MODEL --n_gpu_layers -1 --n_ctx 16384 --port 8090 --host 127.0.0.1 --chat_format chatml > locomo_run/server.log 2>&1 & echo \$! > ~/jpwork/locomo_run/server.pid"
  for i in $(seq 1 60); do
    sleep 10
    $SSH 'curl -s -m 20 127.0.0.1:8090/v1/models' | grep -q gguf && break
  done
  echo "server up $(date +%H:%M)"
  nohup bash -c "while true; do ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N -L 18090:127.0.0.1:8090 $MAC; sleep 5; done" > /tmp/locomo_tunnel.log 2>&1 &
  echo $! > /tmp/locomo_tunnel.pid
  echo "tunnel started"
  ;;
stop)
  [ -f /tmp/locomo_tunnel.pid ] && pkill -P $(cat /tmp/locomo_tunnel.pid); kill $(cat /tmp/locomo_tunnel.pid) 2>/dev/null
  $SSH 'p=$(cat ~/jpwork/locomo_run/server.pid); kill $p; sleep 3; kill -9 $p 2>/dev/null; lsof -nP -iTCP:8090 -sTCP:LISTEN | grep -c LISTEN'
  ;;
esac
