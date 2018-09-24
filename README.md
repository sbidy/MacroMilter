# Version 3.5.2 is available
[![Build Status](https://travis-ci.com/sbidy/MacroMilter.svg?branch=master)](https://travis-ci.com/sbidy/MacroMilter)

Changelog:
 - Fixed some bugs (zip handling, access rights ...)
 - Preparation for python 3 compatibility
 - some minor changes and improvements
 - standardize the log messages

## Contributing
I need some code review and help to make this milter better! If you find some bugs or the code is "creepy" -> feel free to contribute :)

To contribute, please fork this repository and make pull requests to the master or testing branch.

## Branches
#### master = production grade and tested implementation

#### testing = only for testing and non-prod. environments

## Abstract
This python based milter for the Sendmail and Postfix e-mail servers (mail-filter) checks an incoming mail for MS 20xx Office attachments. If a MS Office file is attached to the mail it will be scanned for suspicious VBA macro code. Documents with malicious macros are removed and replaced by harmless text files or will be rejected to the sender (see config.ini).

### Supported Office formats:
- Word 97-2003 (.doc, .dot), Word 2007+ (.docm, .dotm)
- Excel 97-2003 (.xls), Excel 2007+ (.xlsm, .xlsb)
- PowerPoint 97-2003 (.ppt), PowerPoint 2007+ (.pptm, .ppsm)
- Word 2003 XML (.xml)
- Word/Excel Single File Web Page / MHTML (.mht)
- Publisher (.pub)

Paper (german only) -> [download link](https://github.com/sbidy/MacroMilter/blob/master/Bachelorarbeit%20-%20Traub%2C%20Stephan.pdf)

Video / Talk (german only) -> [HdM-events](http://events.mi.hdm-stuttgart.de/2016-06-29-mi-pr%C3%A4sentationstag-ss16/MacroMilter%3A%20Malware-Filter%20f%C3%BCr%20E-Mails)

Chemnitzer Linux Tage 2018 - Talk -> [CLT2018](https://chemnitzer.linux-tage.de/2018/de/programm/beitrag/304)

*The repo is optimized for Visual Studio*
## Features
* Parsing VBA macros for suspicious code and function calls
* Uses the milter interface at postfix and sendmail
* Easy to implement
* Not based on virus heuristics (high detection rate)
* Whitelisting
* Creates a hashtable for already scanned files (prevents rescans)
* Runs at the pre-queue at postfix

## Dependencies
This milter use the functionality from the oletools (https://bitbucket.org/decalage/oletools) and pymilter (https://pythonhosted.org/milter/) projects.

## Installation

### Debian and Ubuntu
Download the "ubuntu_install.sh" script from the repo - [install_ubuntu.sh](https://raw.githubusercontent.com/sbidy/MacroMilter/master/macromilter/install_ubuntu.sh). It creates and downloads all required files and packages.

### Fedora
```bash
dnf install macromilter
systemctl enable --now macromilter.service

postconf -e smtpd_milters=inet:127.0.0.1:3690 milter_default_action=accept
systemctl reload postfix.service
```

### Red Hat Enterprise Linux and CentOS
```bash
yum install epel-release  # Only if EPEL is not already enabled

yum install macromilter
systemctl enable --now macromilter.service

postconf -e smtpd_milters=inet:127.0.0.1:3690 milter_default_action=accept
systemctl reload postfix.service
```

## User whitelist
To allow a user or whole domain to send false-positive VAB-Macro-Mails, enter only the user mail address (xyz@domain.com) or the  domain (@domain.com). See config.ini for more details.

## TBD
* Add some advanced logic to the whitelist
* Code need some love :-)
* Config-File error handling
* Testing / performance
* HTML-Dashboard
* Setup-package for pip

## Authors
Stephan Traub - Sbidy -> https://github.com/sbidy

Robert Scheck - robert-scheck -> https://www.robert-scheck.de/

## Credits
Philippe Lagadec https://github.com/decalage2 - oletools

Stuart D. Gathman https://github.com/sdgathman - pymilter

## License
The MIT License (MIT)

