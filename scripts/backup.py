#!/usr/bin/env python3
import os
import subprocess
import boto3
from datetime import datetime, timedelta, timezone
import argparse
import configparser

def load_aws_credentials(credentials_file):
    config = configparser.ConfigParser()
    config.read(credentials_file)
    if 'default' not in config:
        raise KeyError("'default' section is missing in the credentials file")
    return config['default']['aws_access_key_id'], config['default']['aws_secret_access_key']

def send_notification(title, message, config_path=None):
    if os.path.exists("/usr/local/bin/apprise") and config_path and os.path.exists(config_path):
        subprocess.run(["/usr/local/bin/apprise", "-t", title, "-b", message, "--config", config_path])
    else:
        print(f"Notification skipped: Apprise config not provided or not found.")

def rotate_backups(dest, retain_count=None, exp_date=None, aws_endpoint=None, aws_access_key=None, aws_secret_key=None):
    s3 = boto3.client('s3', endpoint_url=aws_endpoint, aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key)
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
    archive_name = f"{config['name_backup']}_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')}.gz"
    tmp_path = os.path.join(config['tmp_dir'], archive_name)
    dump_path = tmp_path.replace('.gz', '.sql')
    try:
        if config.get("container_name"):
            container_dump_path = f"/tmp/{archive_name.replace('.gz', '.sql')}"
            print(f"Starting PostgreSQL backup in container: {config['container_name']}")
            subprocess.run([
                "docker", "exec", config["container_name"], "pg_dump",
                f"postgresql://{config['database_user']}:{config['database_password']}@"
                f"{config['database_host']}:{config['database_port']}/{config['database_name']}",
                "-f", container_dump_path
            ], check=True)
            print(f"Copying dump file from container: {container_dump_path}")
            subprocess.run([
                "docker", "cp", f"{config['container_name']}:{container_dump_path}", dump_path
            ], check=True)
            subprocess.run([
                "docker", "exec", config["container_name"], "rm", container_dump_path
            ], check=True)
        else:
            with open(dump_path, 'wb') as f:
                subprocess.run([
                    "pg_dump", f"postgresql://{config['database_user']}:{config['database_password']}@"
                    f"{config['database_host']}:{config['database_port']}/{config['database_name']}"
                ], stdout=f, check=True)
        subprocess.run(["gzip", dump_path], check=True)
        aws_access_key, aws_secret_key = load_aws_credentials(config['credentials_file'])
        upload_to_s3(tmp_path, config['aws_dest'], config['aws_endpoint'], aws_access_key, aws_secret_key)
    except Exception as e:
        send_notification("Backup Failed", f"Postgres backup failed: {str(e)}")

def backup_mysql(config):
    archive_name = f"{config['name_backup']}_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')}.gz"
    tmp_path = os.path.join(config['tmp_dir'], archive_name)
    dump_path = tmp_path.replace('.gz', '.sql')
    try:
        if config.get("container_name"):
            container_dump_path = f"/tmp/{archive_name.replace('.gz', '.sql')}"
            print(f"Starting MySQL backup in container: {config['container_name']}")
            subprocess.run([
                "docker", "exec", config["container_name"], "mysqldump",
                "-u", config['database_user'], f"--password={config['database_password']}",
                config['database_name'], "-r", container_dump_path
            ], check=True)
            print(f"Copying dump file from container: {container_dump_path}")
            subprocess.run([
                "docker", "cp", f"{config['container_name']}:{container_dump_path}", dump_path
            ], check=True)
            subprocess.run([
                "docker", "exec", config["container_name"], "rm", container_dump_path
            ], check=True)
        else:
            with open(dump_path, 'wb') as f:
                subprocess.run([
                    "mysqldump", "-u", config['database_user'], f"--password={config['database_password']}",
                    config['database_name']
                ], stdout=f, check=True)
        subprocess.run(["gzip", dump_path], check=True)
        aws_access_key, aws_secret_key = load_aws_credentials(config['credentials_file'])
        upload_to_s3(tmp_path, config['aws_dest'], config['aws_endpoint'], aws_access_key, aws_secret_key)
    except Exception as e:
        send_notification("Backup Failed", f"MySQL backup failed: {str(e)}")

def backup_mongo(config):
    archive_name = f"{config['name_backup']}_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')}.gz"
    tmp_path = os.path.join(config['tmp_dir'], archive_name)
    try:
        if config.get("container_name"):
            container_dump_path = f"/tmp/{archive_name.replace('.gz', '')}"
            print(f"Starting MongoDB backup in container: {config['container_name']}")
            subprocess.run([
                "docker", "exec", config["container_name"], "mongodump",
                "--db", config['database_name'], "--archive", container_dump_path
            ], check=True)
            print(f"Copying dump file from container: {container_dump_path}")
            subprocess.run([
                "docker", "cp", f"{config['container_name']}:{container_dump_path}", tmp_path.replace('.gz', '')
            ], check=True)
            subprocess.run([
                "docker", "exec", config["container_name"], "rm", container_dump_path
            ], check=True)
        else:
            subprocess.run([
                "mongodump", "--db", config['database_name'], "--archive", tmp_path.replace('.gz', '')
            ], check=True)
        subprocess.run(["gzip", tmp_path.replace('.gz', '')], check=True)
        aws_access_key, aws_secret_key = load_aws_credentials(config['credentials_file'])
        upload_to_s3(tmp_path, config['aws_dest'], config['aws_endpoint'], aws_access_key, aws_secret_key)
    except Exception as e:
        send_notification("Backup Failed", f"MongoDB backup failed: {str(e)}")

def upload_to_s3(file_path, dest, aws_endpoint, aws_access_key, aws_secret_key):
    s3 = boto3.client(
        's3',
        endpoint_url=aws_endpoint,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    bucket, key = dest.split('/', 1)
    try:
        print(f"Uploading {file_path} to S3...")
        s3.upload_file(file_path, bucket, key)
        print(f"File uploaded: {file_path}")
        os.remove(file_path)
    except Exception as e:
        send_notification("Upload Failed", f"Failed to upload {file_path} to S3: {str(e)}")
        print(f"Upload failed: {file_path} - {str(e)}")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Backup Universal Script")
    parser.add_argument("-t", "--database_type", required=True, help="Type of the database (postgres, mysql, mongo)")
    parser.add_argument("-n", "--name_backup", required=True, help="Name of the backup")
    parser.add_argument("-d", "--aws_dest", required=True, help="AWS S3 destination (bucket/prefix)")
    parser.add_argument("-u", "--database_user", required=True, help="Database user")
    parser.add_argument("-p", "--database_password", required=True, help="Database password")
    parser.add_argument("-H", "--database_host", required=True, help="Database host")
    parser.add_argument("-P", "--database_port", required=True, type=int, help="Database port")
    parser.add_argument("-r", "--retain_count", type=int, help="Number of backups to retain")
    parser.add_argument("-e", "--exp_date", type=int, help="Expiration date in seconds (optional)")
    parser.add_argument("--container_name", help="Docker container name (optional)")
    parser.add_argument("--aws_endpoint", help="AWS S3 endpoint (optional)")
    parser.add_argument("--tmp_dir", default="/tmp", help="Temporary directory for backups")
    parser.add_argument("--aws_access_key", help="AWS access key (optional)")
    parser.add_argument("--aws_secret_key", help="AWS secret key (optional)")
    parser.add_argument("--credentials_file", required=True, help="Path to the AWS credentials file")
    parser.add_argument("--apprise_config", help="Path to the Apprise configuration file (optional)")
    return vars(parser.parse_args())

if __name__ == "__main__":
    config = parse_arguments()

    if config["database_type"] == "postgres":
        backup_postgres(config)
    elif config["database_type"] == "mysql":
        backup_mysql(config)
    elif config["database_type"] == "mongo":
        backup_mongo(config)

    aws_access_key, aws_secret_key = load_aws_credentials(config["credentials_file"])
    rotate_backups(config["aws_dest"], config.get("retain_count"), config.get("exp_date"), config.get("aws_endpoint"), aws_access_key, aws_secret_key)

    if config.get("apprise_config"):
        send_notification("Backup Completed", f"Backup {config['name_backup']} completed successfully.", config["apprise_config"])
    else:
        print("No Apprise configuration provided. Skipping notification.")
