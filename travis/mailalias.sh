  #!/bin/bash
  sudo chmod 777 /home/travis/build/sbidy/MacroMilter/travis/readmail.py
  sudo chown travis:travis /home/travis/build/sbidy/MacroMilter/travis/readmail.py
  sudo echo "test: |/home/travis/build/sbidy/MacroMilter/travis/readmail.py >> /home/travis/build/sbidy/MacroMilter/travis/mail.txt" >> /etc/aliases
  sudo newaliases
  sudo cat /etc/aliases
