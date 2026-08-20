echo 'Metropolis0!' > /tmp/pwd.txt
sudo -S systemctl stop audio-kiosk.service < /tmp/pwd.txt
sudo -S kill -9 $(pgrep -f vllm) < /tmp/pwd.txt
sleep 2
sudo -S systemctl stop vllm.service < /tmp/pwd.txt
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount -t ntfs-3g /dev/sdb1 /mnt/models -o rw < /tmp/pwd.txt
sudo -S rm -rf /mnt/models/whisper-large-v3-turbo-ct2 < /tmp/pwd.txt
sudo -S /home/ubuntu/ai_kiosk/bin/ct2-transformers-converter --model /mnt/models/whisper-large-v3-turbo --output_dir /mnt/models/whisper-large-v3-turbo-ct2 --copy_files tokenizer.json preprocessor_config.json --quantization float16 < /tmp/pwd.txt
sudo -S sync < /tmp/pwd.txt
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount /mnt/models < /tmp/pwd.txt
sudo -S systemctl start vllm.service audio-kiosk.service < /tmp/pwd.txt
rm /tmp/pwd.txt
