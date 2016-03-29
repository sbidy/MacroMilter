## IMPORTANT: NEW IN 2.8 !!!!
Please create the "log" folder /var/log/macromilter/log or <LOG_DIR>/log !!

## Contributing
I need some code review and help to make this milter better! If you find some bugs or the code is "creepy" -> feel free to contribute :)

To contribute, please fork this repository and make pull requests to the develop branch.
## Abstract
This python based milter (mail-filter) checks an incoming mail for MS 200x Office attachments (doc, xls, ppt, xlsm, docm, rtf). If a MS Office file is attached to the mail it will be scanned for suspicious VBA macro code. After the milter parsed the attachment a kind of risk level will be defined for that document. If the risk level reaches a defined value – the mail will be rejected to the sender.

*The repo is optimized for Visual Studio*
## Features
* Parsing VBA macros for suspicious code and function calls
* Uses the milter interface at postfix and sendmail
* Easy to implement
* Not based on virus heuristics (high detection rate)
* Only reject if a threshold is reached
* Whitelisting
* Creates a hashtable for allready scanned files (prevents rescans)
* Runns at the pre-queue at postfix

## Dependencies
This milter use the functionality from the oletools (https://bitbucket.org/decalage/oletools) and pymilter (https://pythonhosted.org/milter/) projects.

## Installation (Ubuntu with upstart)
1. download the oletools (https://bitbucket.org/decalage/oletools) and pymilter (https://pythonhosted.org/milter/) packages
2. step through the following bash. In some cases, you need to edit paths or install some missing dependencies!
```bash
# create files and folders
mkdir /etc/macromilter
mkdir /etc/macromilter/log
# only needed for a chroot env
# mkdir /var/spool/postfix/etc/milter

# install macromilter dependencies
apt-get update
apt-get install python2.7 python2.7-dev libmilter-dev libmilter1.0.1 python-pip

# install oletools
pip install oletools

# install pymilter --> maybe you need some addtional dependencies - see doc
pip install pymilter

# copy the python script
cp macromilter.py /etc/macromilter/
# setup upstart config
cp MacroMilter.conf /etc/init/
initctl reload-configuration
# create the whitelist
touch /etc/macromilter/whitelist.list

# set chown for postfix
chown postfix:postfix -R /etc/macromilter
# only needed if you run the milter at chroot an with a linux-socket
# chown postfix:postfix -R /var/spool/postfix/etc/milter 

# start and check
service MacroMilter start
tail /var/log/syslog
```
## Installation script OpenSuse
```bash
zypper in python-devel sendmail-devel gcc python-pip git
pip install pymilter
pip install oletools
git clone https://github.com/sbidy/MacroMilter
#git clone https://github.com/Gulaschcowboy/MacroMilter
mkdir -p /etc/macromilter/
mkdir -p /var/log/macromilter/
cp MacroMilter/MacroMilter/macromilter.py /etc/macromilter/
cp MacroMilter/MacroMilter/macromilter.service /etc/systemd/system/
cp MacroMilter/MacroMilter/macromilter.logrotate /etc/logrotate.d/

touch /etc/macromilter/whitelist.list
chown postfix:postfix /var/log/macromilter/

systemctl daemon-reload
systemctl start macromilter.service
systemctl status macromilter.service
systemctl enable macromilter.service

postconf -e smtpd_milters=inet:127.0.0.1:3690
postconf -e milter_default_action=accept

rcpostfix reload
```
## User whitelist
To allow a user or domain to send VAB-Macro-Mails enter only the user mail address (xyz@domain.com) or the whole domain (@domain.com) in the whitelist.list file. Only one entry per line.

Be careful with whitelisting! In some cases the better way is to block all Office_Macro_files with for example ClamAV.

##VBA_OLE_Malware_MD5.txt
This file contains more than 500 MD5 Hashes of suspicious Office documents.

## TBD
* Calculate a better reject level
* Use the full features ot the olevba
* Add some advanced logic to the whitelist
* Code need some love :-)

## Authors
Stephan Traub - Sbidy -> https://github.com/sbidy

## License
The MIT License (MIT)

