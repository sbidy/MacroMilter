# Version 3.0 is available
Changelog:
  - Code cleanup and removed the multi-thread feature
  - Add a config.ini file for the milter configuration 
  - Update to the new mraptor feature (oletools)
  - Adapt logging from mraptor
  - Remove performance logging
  - BugFix for #9 and #10
  - Update documentation and add a install script for Ubuntu

## Contributing
I need some code review and help to make this milter better! If you find some bugs or the code is "creepy" -> feel free to contribute :)

To contribute, please fork this repository and make pull requests to the master branch.
## Abstract
This python based milter for the Sendmail and Postfix e-mail servers (mail-filter) checks an incoming mail for MS 20xx Office attachments. If a MS Office file is attached to the mail it will be scanned for suspicious VBA macro code. Documents with malicious macros are removed and replaced by harmless text files or will be rejected to the sender (see config.ini).

### Supported Office formats:
- Word 97-2003 (.doc, .dot), Word 2007+ (.docm, .dotm)
- Excel 97-2003 (.xls), Excel 2007+ (.xlsm, .xlsb)
- PowerPoint 97-2003 (.ppt), PowerPoint 2007+ (.pptm, .ppsm)
- Word 2003 XML (.xml)
- Word/Excel Single File Web Page / MHTML (.mht)
- Publisher (.pub)

Paper (german only): https://github.com/sbidy/MacroMilter/blob/master/Bachelorarbeit%20-%20Traub%2C%20Stephan.pdf

*The repo is optimized for Visual Studio*
## Features
* Parsing VBA macros for suspicious code and function calls
* Uses the milter interface at postfix and sendmail
* Easy to implement
* Not based on virus heuristics (high detection rate)
* Whitelisting
* Creates a hashtable for already scanned files (prevents rescans)
* Runns at the pre-queue at postfix

## Dependencies
This milter use the functionality from the oletools (https://bitbucket.org/decalage/oletools) and pymilter (https://pythonhosted.org/milter/) projects.

## Installation

### Debian and Ubuntu
Download the "ubuntu_install.sh" script from the repo (https://raw.githubusercontent.com/sbidy/MacroMilter/master/macromilter/install_ubuntu.sh). It creates and downloads all required files and packages.

### Fedora
```
dnf install macromilter
systemctl enable --now macromilter.service

postconf -e smtpd_milters=inet:127.0.0.1:3690 -e milter_default_action=accept
systemctl reload postfix.service
```

### openSUSE and SUSE Linux Enterprise Server
```
bash
zypper in python-devel sendmail-devel gcc python-pip git
pip install pymilter
pip install oletools
git clone https://github.com/sbidy/MacroMilter
#git clone https://github.com/Gulaschcowboy/MacroMilter
mkdir -p /etc/macromilter/
mkdir -p /var/log/macromilter/
mkdir /var/log/macromilter/log
cp MacroMilter/MacroMilter/macromilter.py /etc/macromilter/
cp MacroMilter/MacroMilter/macromilter.service /etc/systemd/system/
cp MacroMilter/MacroMilter/macromilter.logrotate /etc/logrotate.d/

touch /etc/macromilter/whitelist.list
chown postfix:postfix /var/log/macromilter/

systemctl daemon-reload
systemctl enable --now macromilter.service
systemctl status macromilter.service
postconf -e smtpd_milters=inet:127.0.0.1:3690 -e milter_default_action=accept
rcpostfix reload
```

### Red Hat Enterprise Linux and CentOS
```
yum install epel-release  # Only if EPEL is not already enabled

yum install macromilter
systemctl enable --now macromilter.service

postconf -e smtpd_milters=inet:127.0.0.1:3690 -e milter_default_action=accept
systemctl reload postfix.service
```

## User whitelist
To allow a user or whole domain to send false-positive VAB-Macro-Mails, enter only the user mail address (xyz@domain.com) or the  domain (@domain.com). See config.ini for more details.

Be careful with whitelisting! :-)

## TBD
* Add some advanced logic to the whitelist
* Code need some love :-)
* Config-File error handling
* Testing / performance
* HTML-Dashboard
* Setup-package for pip

## Authors
Stephan Traub - Sbidy -> https://github.com/sbidy

heinrichheine -> https://github.com/heinrichheine

## Credits
Philippe Lagadec https://github.com/decalage2 - oletools

Stuart D. Gathman https://github.com/sdgathman - pymilter

## License
The MIT License (MIT)

