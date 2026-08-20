echo 'Metropolis0!' > /tmp/pwd.txt
sudo -S mount -t ntfs-3g /dev/sdb1 /mnt/models -o rw < /tmp/pwd.txt
/home/ubuntu/ai_kiosk/bin/ct2-transformers-converter --model /mnt/models/whisper-large-v3-turbo --output_dir /mnt/models/whisper-large-v3-turbo-ct2 --copy_files tokenizer.json preprocessor_config.json --quantization float16
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount /mnt/models < /tmp/pwd.txt
sudo -S systemctl start audio-kiosk.service < /tmp/pwd.txt
rm /tmp/pwd.txt
