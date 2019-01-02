#!/usr/bin/env python
import email
import sys

msg = ""
for line in sys.stdin.read().split('\n'):
    print(line)
    msg += line
    
f = open("/home/travis/build/sbidy/MacroMilter/travis/mail.txt", "w")
f.write(msg) 
