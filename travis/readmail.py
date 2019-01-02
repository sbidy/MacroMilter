#!/usr/bin/env python
import email
import sys

msg = email.message_from_file(sys.stdin)
f = open("/home/travis/build/sbidy/MacroMilter/travis/mail.txt", "w")
f.write(msg) 
