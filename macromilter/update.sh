#!/bin/bash
rm macromilter.py
wget https://raw.githubusercontent.com/sbidy/MacroMilter/master/MacroMilter/macromilter.py
service MacroMilter restart

tail -n 100 -f /etc/macromilter/run.log
