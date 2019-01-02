  #!/bin/bash
  cat /home/travis/travis/readmail.py
  sudo echo "test: |/home/travis/travis/readmail.py" >> /etc/aliases
  sudo newaliases
