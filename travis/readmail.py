#!/usr/bin/env python
import email
import sys

msg = email.message_from_file(sys.stdin)
print(msg)
