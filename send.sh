#!/bin/bash

#for normal Linux
notify-send -t 5000 "$1\n" "$2"

#notify-send equivalent for LXSS (Make windows process that listens for changes on log.txt)
#echo -e "\r\n$1\r\n$2\r\n--------\r\n" >> /mnt/f/code/Backups/BackgroundNotifier/notify/log.txt
