## Ansible role for Backup Mongo.
___

This role archives files using tar.gz. It is also possible to delete files, by number, or by time.
Today this role can backup only mongodb inside docker container

```
USAGE: 

in defaults/main.yml set 

---
backup_notifications:
  enabled: true 
  apprise_target: 
  requirements:
    - python3
    - python3-pip
    - python3-setuptools

backup:
  aws_access_key: ""
  aws_secret_key: ""
  paths: []
  #  - name_backup: super-backup
  #    src_backup: /etc/network
  #    tmp_dir: /tmp
  #    aws_dest: ""
  #    retain_count: 5
  #    container_name: name
  #    database_name: name
  #    filter_date: '"5 min ago"'
  #    cron:
  #         minute: "*"
  #         hour: "*"
  #         day: "*"
  #         weekday: "*"
  #         month: "*"


```
