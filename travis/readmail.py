#!/usr/bin/env python
import email
import sys

msg = email.message_from_file(sys.stdin)
f = open("mail.txt", "w")
f.write(msg) 
