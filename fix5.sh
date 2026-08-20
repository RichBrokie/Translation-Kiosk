echo 'Metropolis0!' > /tmp/pwd.txt
sudo -S systemctl stop audio-kiosk.service vllm.service < /tmp/pwd.txt
rm -rf /home/ubuntu/whisper-large-v3-turbo-ct2
/home/ubuntu/ai_kiosk/bin/ct2-transformers-converter --model /mnt/models/whisper-large-v3-turbo --output_dir /home/ubuntu/whisper-large-v3-turbo-ct2 --copy_files tokenizer.json preprocessor_config.json --quantization float16
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount -t ntfs-3g /dev/sdb1 /mnt/models -o rw < /tmp/pwd.txt
sudo -S rm -rf /mnt/models/whisper-large-v3-turbo-ct2 < /tmp/pwd.txt
sudo -S cp -r /home/ubuntu/whisper-large-v3-turbo-ct2 /mnt/models/ < /tmp/pwd.txt
sudo -S sync < /tmp/pwd.txt
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount /mnt/models < /tmp/pwd.txt
sudo -S systemctl start vllm.service audio-kiosk.service < /tmp/pwd.txt
rm /tmp/pwd.txt
