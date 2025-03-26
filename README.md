## Ansible Role for Backup (Postgres, MySQL, MongoDB)

This role automates the backup process for databases (Postgres, MySQL, MongoDB) to S3-compatible storage. It supports cron job configuration, notification via Apprise, and backup rotation.

### Requirements

- Python 3
- AWS CLI
- Apprise (optional for notifications)

### Role Variables

```yaml
backup:
  database_type: ""  # postgres, mysql, mongo
  name_backup: ""  # Name of the backup
  database_name: ""  # Database name
  database_user: ""  # Database user
  database_password: ""  # Database password
  database_host: "localhost"  # Database host
  database_port: 5432  # Database port
  tmp_dir: "/tmp"  # Temporary directory for backups
  aws_dest: ""  # S3 destination (e.g., s3://bucket-name/prefix)
  aws_endpoint: ""  # S3 endpoint URL
  retain_count: 5  # Number of backups to retain
  exp_date: null  # Expiration in seconds
  apprise_config: "/etc/backup/apprise_config"  # Apprise config path
  cron:
    minute: "0"
    hour: "2"
    day: "*"
    month: "*"
    weekday: "*"
  notifications:
    enabled: true  # Enable notifications
    apprise_target: ""  # Apprise target URL
```

### Usage

1. Define the variables in `defaults/main.yml` or override them in your playbook.
2. Run the role to configure backups:
   ```bash
   ansible-playbook -i inventory playbook.yml
   ```
3. Verify that the backup script is copied to `/usr/local/bin/backup_universal/backup.py` on the target host.
4. Check the cron job configuration in `/etc/cron.d/backup_cron`.

### Example Playbook

```yaml
- hosts: all
  roles:
    - role: backup_universal
      vars:
        backup:
          database_type: "postgres"
          name_backup: "example_backup"
          database_name: "example_db"
          database_user: "user"
          database_password: "password"
          database_host: "localhost"
          database_port: 5432
          tmp_dir: "/tmp"
          aws_dest: "s3://my-bucket/backups"
          aws_endpoint: "https://s3.example.com"
          retain_count: 7
          notifications_enabled: true
          cron:
            minute: "0"
            hour: "3"
```