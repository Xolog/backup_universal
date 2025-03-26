import os
import subprocess
import boto3
from datetime import datetime, timedelta, timezone
import argparse

def send_notification(title, message, config_path="/etc/backup/apprise_config"):
    if os.path.exists("/usr/local/bin/apprise") and os.path.exists(config_path):
        subprocess.run(["/usr/local/bin/apprise", "-t", title, "-b", message, "--config", config_path])

def rotate_backups(dest, retain_count=None, exp_date=None, aws_endpoint=None):
    s3 = boto3.client('s3', endpoint_url=aws_endpoint)
    bucket, prefix = dest.split('/', 1)
    objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get('Contents', [])
    sorted_objects = sorted(objects, key=lambda x: x['LastModified'])

    if retain_count:
        for obj in sorted_objects[:-retain_count]:
            s3.delete_object(Bucket=bucket, Key=obj['Key'])

    if exp_date:
        exp_date = datetime.now(timezone.utc) - timedelta(seconds=int(exp_date))
        for obj in sorted_objects:
            if obj['LastModified'] < exp_date:
                s3.delete_object(Bucket=bucket, Key=obj['Key'])

def backup_postgres(config):
    archive_name = f"{config['name_backup']}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.gz"
    tmp_path = os.path.join(config['tmp_dir'], archive_name)
    try:
        if config.get("container_name"):
            subprocess.run([
                "docker", "exec", config["container_name"], "pg_dump",
                f"postgresql://{config['database_user']}:{config['database_password']}@"
                f"{config['database_host']}:{config['database_port']}/{config['database_name']}"
            ], stdout=subprocess.PIPE, check=True)
        else:
            subprocess.run([
                "pg_dump", f"postgresql://{config['database_user']}:{config['database_password']}@"
                f"{config['database_host']}:{config['database_port']}/{config['database_name']}"
            ], stdout=subprocess.PIPE, check=True)
        subprocess.run(["gzip", tmp_path], check=True)
        upload_to_s3(tmp_path, config['aws_dest'], config['aws_endpoint'])
    except Exception as e:
        send_notification("Backup Failed", f"Postgres backup failed: {str(e)}")

def backup_mysql(config):
    archive_name = f"{config['name_backup']}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.gz"
    tmp_path = os.path.join(config['tmp_dir'], archive_name)
    try:
        if config.get("container_name"):
            subprocess.run([
                "docker", "exec", config["container_name"], "mysqldump",
                "-u", config['database_user'], f"--password={config['database_password']}",
                config['database_name']
            ], stdout=subprocess.PIPE, check=True)
        else:
            subprocess.run([
                "mysqldump", "-u", config['database_user'], f"--password={config['database_password']}",
                config['database_name']
            ], stdout=subprocess.PIPE, check=True)
        subprocess.run(["gzip", tmp_path], check=True)
        upload_to_s3(tmp_path, config['aws_dest'], config['aws_endpoint'])
    except Exception as e:
        send_notification("Backup Failed", f"MySQL backup failed: {str(e)}")

def backup_mongo(config):
    archive_name = f"{config['name_backup']}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.gz"
    tmp_path = os.path.join(config['tmp_dir'], archive_name)
    try:
        if config.get("container_name"):
            subprocess.run([
                "docker", "exec", config["container_name"], "mongodump",
                "--db", config['database_name'], "--archive", tmp_path
            ], check=True)
        else:
            subprocess.run([
                "mongodump", "--db", config['database_name'], "--archive", tmp_path
            ], check=True)
        subprocess.run(["gzip", tmp_path], check=True)
        upload_to_s3(tmp_path, config['aws_dest'], config['aws_endpoint'])
    except Exception as e:
        send_notification("Backup Failed", f"MongoDB backup failed: {str(e)}")

def upload_to_s3(file_path, dest, aws_endpoint):
    s3 = boto3.client('s3', endpoint_url=aws_endpoint)
    bucket, key = dest.split('/', 1)
    try:
        s3.upload_file(file_path, bucket, key)
        os.remove(file_path)
    except Exception as e:
        send_notification("Upload Failed", f"Failed to upload {file_path} to S3: {str(e)}")

def configure_cron(config):
    cron_job = (
        f"{config['cron']['minute']} {config['cron']['hour']} {config['cron']['day']} "
        f"{config['cron']['month']} {config['cron']['weekday']} "
        f"/usr/local/bin/backup_universal/backup.py"
    )
    cron_file = "/etc/cron.d/backup_cron"
    with open(cron_file, "w") as f:
        f.write(cron_job + "\n")
    os.chmod(cron_file, 0o644)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Backup Universal Script")
    parser.add_argument("-t", "--database_type", required=True, help="Type of the database (postgres, mysql, mongo)")
    parser.add_argument("-n", "--name_backup", required=True, help="Name of the backup")
    parser.add_argument("-d", "--aws_dest", required=True, help="AWS S3 destination (bucket/prefix)")
    parser.add_argument("-u", "--database_user", required=True, help="Database user")
    parser.add_argument("-p", "--database_password", required=True, help="Database password")
    parser.add_argument("-h", "--database_host", required=True, help="Database host")
    parser.add_argument("-P", "--database_port", required=True, type=int, help="Database port")
    parser.add_argument("-r", "--retain_count", type=int, help="Number of backups to retain")
    parser.add_argument("-e", "--exp_date", type=int, help="Expiration date in seconds (optional)")
    parser.add_argument("--container_name", help="Docker container name (optional)")
    parser.add_argument("--aws_endpoint", help="AWS S3 endpoint (optional)")
    parser.add_argument("--tmp_dir", default="/tmp", help="Temporary directory for backups")
    return vars(parser.parse_args())

if __name__ == "__main__":
    config = parse_arguments()

    if config["database_type"] == "postgres":
        backup_postgres(config)
    elif config["database_type"] == "mysql":
        backup_mysql(config)
    elif config["database_type"] == "mongo":
        backup_mongo(config)

    rotate_backups(config["aws_dest"], config.get("retain_count"), config.get("exp_date"), config.get("aws_endpoint"))
    configure_cron(config)
