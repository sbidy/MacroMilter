# MacroMilter
## Help wanted
I need some code review and help to make this milter better! If you find some bugs or the code is "creepy" -> feel free to contribute :)
## Abstract
This python based milter (mail-filter) checks an incoming mail for MS 200x Office attachments (doc, xls, ppt). If a MS Office file is attached to the mail it will be scanned for suspicious VBA macro code. After the milter parsed the attachment a kind of risk level will be defined for that document. If the risk level reaches a defined value – the mail will be rejected to the sender.

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

## Installation (Ubuntu with upstart)
1. download the oletools (https://bitbucket.org/decalage/oletools) and pymilter (https://pythonhosted.org/milter/) packages
2. step through the following bash. In some cases, you need to edit paths or install some missing dependencies!
```bash
# create files and folders
mkdir /etc/macromilter
mkdir /etc/macromilter/log
# only needed for a chroot env
mkdir /var/spool/postfix/etc/milter
touch /etc/macromilter/whitelist.list

# setup upstart config
cp MacroMilter.conf /etc/init/
initctl reload-configuration

# install macromilter dependencies
apt-get update
apt-get install python2.7 python2.7-dev libmilter-dev libmilter1.0.1

# install oletools
tar -zxvf oletools-0.41.tar.gz
cd oletools-0.41
python setup.py install

# install pymilter --> maybe you need some addtional dependencies - see doc
tar -zxvf pymilter-1.0.tar.gz
cd pymilter-1.0
python setup.py install

cp macromilter.py /etc/macromilter/

# set chown for postfix
chown postfix:postfix -R /etc/macromilter
# only needed if you run the milter at chroot an with a linux-socket
chown postfix:postfix -R /var/spool/postfix/etc/milter 

# start and check
service MacroMilter start
tail /var/log/syslog
```
## Authors
Stephan Traub - Sbidy -> https://github.com/sbidy

## License
The MIT License (MIT)

Copyright (c) 2016 Stephan Traub - audius GmbH, www.audius.de

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
 
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
