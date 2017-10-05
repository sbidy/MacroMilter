#!/bin/bash
cd /usr/bin/
rm macromilter.py
wget https://raw.githubusercontent.com/sbidy/MacroMilter/master/MacroMilter/macromilter.py
service MacroMilter restart

