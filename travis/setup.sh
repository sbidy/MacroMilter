#!/bin/bash
# create files and folders
mkdir /etc/macromilter/
mkdir -p /var/log/macromilter/
# only needed for a chroot env
# mkdir /var/spool/postfix/etc/milter

# copy the python script
cp ./macromilter/macromilter.py /usr/bin/
cp ./macromilter/config.ini /etc/macromilter/

# setup upstart config
cp ./macromilter/MacroMilter.conf /etc/init/
initctl reload-configuration

# set chown for postfix
chown postfix:postfix -R /etc/macromilter
chown postfix:postfix -R /var/log/macromilter
chown postfix:postfix /usr/bin/macromilter.py

# start and check
service MacroMilter start
tail /var/log/macromilter/macromilter.log