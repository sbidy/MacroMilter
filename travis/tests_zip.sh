#!/bin/bash
! sendemail -f travis@localhost -t travis@localhost -m "test" -s localhost -u "test" -a ./test_mails/zipwithinfectedandnotinfectedword.zip -v
