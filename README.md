## Ansible role for Backup Mongo, MySQL and Posrtgres.
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

pg_remote:
  database_name: test
  name_backup: super-backup
  database_user: test
  database_password: test
  database_host: localhost
  database_port: 5433
 
mysql_docker:
  database_name: test
  name_backup: super-backup_mysql
  database_user: test
  database_password: test
  container_name: name


backup:
  aws_access_key: ""
  aws_secret_key: ""
  aws_endpoint: enpoint
  databases:
  - name_backup: super-bassdsds
    database_type: pg_remote
    tmp_dir: /tmp
    database_name: name
    aws_dest: ""
    aws_endpoint: ""
    retain_count: 5
    filter_date: '"5 min ago"'
    cron:
        minute: "*"
        hour: "*"
        day: "*"
        weekday: "*"
        month: "*"
  - name_backup: super-bassdsds
    database_type: mysql_docker
    tmp_dir: /tmp
    container_name: name
    database_name: name
    aws_dest: ""
    aws_endpoint: ""
    retain_count: 5
    filter_date: '"5 min ago"'
    cron:
        minute: "*"
        hour: "*"
        day: "*"
        weekday: "*"
        month: "*