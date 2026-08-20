echo 'Metropolis0!' > /tmp/pwd.txt
sudo -S systemctl stop vllm.service audio-kiosk.service < /tmp/pwd.txt
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount -t ntfs-3g /dev/sdb1 /mnt/models -o rw < /tmp/pwd.txt
sudo -S mv /home/ubuntu/whisper-large-v3-turbo-ct2 /mnt/models/ < /tmp/pwd.txt
sudo -S umount /mnt/models < /tmp/pwd.txt
sudo -S mount /mnt/models < /tmp/pwd.txt
sudo -S systemctl start vllm.service < /tmp/pwd.txt
sudo -S systemctl start audio-kiosk.service < /tmp/pwd.txt
rm /tmp/pwd.txt
