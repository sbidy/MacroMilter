#!/bin/bash
# create files and folders
mkdir /etc/macromilter
mkdir -p /var/log/macromilter/

# only needed for a chroot env
# mkdir /var/spool/postfix/etc/milter

# install macromilter dependencies
apt-get update
apt-get install python2.7 python2.7-dev libmilter-dev libmilter1.0.1 python-pip

# install oletools
pip install oletools
# install pymilter --> maybe you need some addtional dependencies - see doc
pip install pymilter
# install configparser
pip install configparser

# copy the python script
cd /etc/macromilter/
wget https://raw.githubusercontent.com/sbidy/MacroMilter/master/macromilter/macromilter.py
wget https://raw.githubusercontent.com/sbidy/MacroMilter/master/macromilter/config.ini
# setup upstart config
cd /etc/init/
wget https://raw.githubusercontent.com/sbidy/MacroMilter/master/macromilter/MacroMilter.conf
initctl reload-configuration

# set chown for postfix
chown postfix:postfix -R /etc/macromilter
chown postfix:postfix -R /var/log/macromilter

# only needed if you run the milter at chroot an with a linux-socket
# chown postfix:postfix -R /var/spool/postfix/etc/milter 

# start and check
service MacroMilter start
tail /var/log/syslog
