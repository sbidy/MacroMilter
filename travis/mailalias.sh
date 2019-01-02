  #!/bin/bash
  cat /home/travis/MacroMilter/travis/readmail.py
  sudo echo "test: |/home/travis/MacroMilter/travis/readmail.py" >> /etc/aliases
  sudo newaliases
