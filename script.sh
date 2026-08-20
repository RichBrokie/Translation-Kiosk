echo 'Metropolis0!' | sudo -S sed -i 's/--port 8000/--port 8000 --max-model-len 8192/' /etc/systemd/system/vllm.service
echo 'Metropolis0!' | sudo -S systemctl daemon-reload
echo 'Metropolis0!' | sudo -S systemctl restart vllm.service
