import boto3
import paramiko

from botocore.exceptions import ClientError
from paramiko import SSHClient
from scp import SCPClient
from typing import Dict, List, Tuple

UBUNTU_AMI = 'ami-0ecb62995f68bb549'
ec2 = boto3.client('ec2')

def create_ssh_client(ip, key_path="log8415-final.pem", username="ubuntu") -> SSHClient:
  """
  Establish and return an SSH connection to an EC2 instance.
  Args:
    ip (str): Public IP address of the EC2 instance
    key_path (str): Path to the .pem private key
    username (str): SSH username

  Returns:
    paramiko.SSHClient: an active SSH client
  """
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username=username, key_filename=key_path)

  return ssh


def upload_files_to_instance(ip, key_path="log8415-final.pem", local_folder='.', distant_folder="~", files=[]):
  """
  Copy a list of files to EC2 instances via SSH and SCP
  Args:
    ip (str): Public IP of an EC2 instance
    key_path (str): Path to the private key (.pem)
    local_folder (str): Local folder containing files
    distant_folder (str): Distant folder where we want to copy files
    files (list[str]): list with filenames to copy
  """
  print(f"Transferring files to the {local_folder} : {files}")

  ssh = create_ssh_client(ip, key_path)

  ssh.exec_command(f"mkdir -p {distant_folder}")

  with SCPClient(ssh.get_transport()) as scp:
    for file in files:
      local_path = f"{local_folder}/{file}"
      remote_path = f"{distant_folder}/{file}"
      scp.put(local_path, remote_path)
      print(f"{file} → {ip}:{remote_path}")

  ssh.close()


def ensure_ports_open(ec2, sg_id, ports):
  """
  Ensure that all given ports are open in the specified security group.
  Args:
    ec2 (boto3.client): EC2 client instance for AWS operations
    sg_id (str): Id of the security group to modify
    ports (list[int]): Ports which needs to be opened
  """
  try:
    sg_info = ec2.describe_security_groups(GroupIds=[sg_id])["SecurityGroups"][0]
    existing_permissions = sg_info.get("IpPermissions", [])
    existing_ports = [p.get("FromPort") for p in existing_permissions if "FromPort" in p]

    for port in ports:
      if port not in existing_ports:
        try:
          ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
              "IpProtocol": "tcp",
              "FromPort": port,
              "ToPort": port,
              "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            }]
          )
          print(f"Added inbound rule for port {port} to SG {sg_id}")
        except ec2.exceptions.ClientError as e:
          if "InvalidPermission.Duplicate" in str(e):
            pass
          else:
            raise
  except ClientError as e:
    print(f"Error while updating security group {sg_id}: {e}")


def get_default_resources(ec2, verbose=False):
  """
  Retrieve default AWS VPC resources (VPC, subnet, and security group),
  and ensure inbound rules for SSH (22) and HTTP (8000) are allowed from anywhere.
  Args:
    ec2 (boto3.client): EC2 client instance for AWS operations
    verbose (bool, optional): If True, prints the retrieved resource IDs. Defaults to False.
  
  Returns:
    tuple: A tuple containing (default_vpc_id, default_subnet_id, default_sg_id) as strings
  """
  # Get the default VPC
  vpcs = ec2.describe_vpcs(Filters=[{'Name': 'is-default', 'Values': ['true']}])
  default_vpc_id = vpcs['Vpcs'][0]['VpcId']

  # Get the first of the default VPC
  subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}])
  default_subnet_id = subnets['Subnets'][0]['SubnetId']
  
  # Get the default security group
  security_groups = ec2.describe_security_groups(
    Filters=[
      {'Name': 'vpc-id', 'Values': [default_vpc_id]},
      {'Name': 'group-name', 'Values': ['default']}
    ]
  )
  default_sg_id = security_groups['SecurityGroups'][0]['GroupId']

  # Open all required ports
  ports_to_open = [22, 80, 3306, 5000]
  ensure_ports_open(ec2, default_sg_id, ports_to_open)
    
  if verbose:
    print(f"default VPC: {default_vpc_id}")
    print(f"default subnet: {default_subnet_id}")
    print(f"default security group: {default_sg_id}")
  
  return default_vpc_id, default_subnet_id, default_sg_id


def launch_instance(instance_name, type, key_name='log8415-final', user_data=''):
  """
  Launch one or multiple EC2 instances with specified configuration and tags.
  
  Args:
    ec2 (boto3.client): EC2 client instance for AWS operations
    type (str): EC2 instance type (e.g., 't2.micro', 't2.large')
    instance_name (str): Base name for the instances (will be suffixed with index)
    key_name (str, optional): Name of the SSH key pair. Defaults to 'vockey'.
  
  Returns:
    instance created
  """
  try:
    _, subnet_id, sg_id = get_default_resources(ec2)
    
    print(f"Launching {instance_name}…")

    response = ec2.run_instances(
      ImageId=UBUNTU_AMI,
      InstanceType=type,
      KeyName=key_name,
      MinCount=1,
      MaxCount=1,
      NetworkInterfaces=[{
        "DeviceIndex": 0,
        "AssociatePublicIpAddress": True,
        "SubnetId": subnet_id,
        "Groups": [sg_id]
      }],
      TagSpecifications=[
        {
          "ResourceType": "instance",
          "Tags": [
            {"Key": "Name", "Value": f"{instance_name}"},
          ]
        }
      ],
      UserData=user_data,
    )
    
    instance_id = response['Instances'][0]['InstanceId']
    print(f"Instance created with ID: {instance_id}")

    waiter = ec2.get_waiter("instance_status_ok")
    waiter.wait(InstanceIds=[instance_id])

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    for reservation in desc["Reservations"]:
      for instance in reservation["Instances"]:
        private_ip = instance.get("PrivateIpAddress", None)
        public_ip = instance.get("PublicIpAddress", None)

    return {
      'public_ip': public_ip,
      'private_ip': private_ip,
      'instance_id': instance_id,
      'is_master': instance_name == 'manager'
    }

  except ClientError as e:
    print(f"Error during launching: {e}")
    return None


def run_ssh_commands(host_ip: str, commands: List) -> None:
  client = create_ssh_client(host_ip)
  for cmd in commands:
    _, stdout, stderr = client.exec_command(cmd)
    stdout.channel.settimeout(15)
    try:
      stdout.read().decode("utf-8")
      err = stderr.read().decode("utf-8")
      if err:
        print(err)
    except Exception as e:
      print(e)
  client.close()


def get_binary_log_coords(host_ip: str):
  client = create_ssh_client(host_ip)
  stdin, stdout, stderr = client.exec_command(
    "sudo mysql -uroot -prootpass -N -e 'SHOW MASTER STATUS;'"
  )
  output = stdout.read().decode("utf-8").strip().split("\t")
  # Columns: File  Position  Binlog_Do_DB  Binlog_Ignore_DB ...
  log_file = output[0]
  log_pos = int(output[1])
  client.close()

  return log_file, log_pos

def check_sakila_installation(instances) -> None:
  """
  Run sysbench to check if sakila is correctly installed on the instances
  
  :param instances: Instances on which sakila is installed
  :type instances: List
  """

  commands = [
    "sudo sysbench /usr/share/sysbench/oltp_read_only.lua --mysql-db=sakila --mysql-user='root' --mysql-password='rootpass' prepare",
    "sudo sysbench /usr/share/sysbench/oltp_read_only.lua --mysql-db=sakila --mysql-user='root' --mysql-password='rootpass' run",
  ]

  for instance in instances:
    run_ssh_commands(instance['public_ip'], commands)

def configure_db_for_replication(instances) -> None:
  source_ip = [inst['private_ip'] for inst in instances if inst['is_master']]
  replica_ips = [inst['private_ip'] for inst in instances if not inst['is_master']]
  count = 1

  log_file = ''
  log_pos = ''

  for instance in instances:
    commands = []

    if instance['is_master']:
      commands = [
        f"sudo sed -i 's/^bind-address.*/bind-address={source_ip[0]}/' /etc/mysql/mysql.conf.d/mysqld.cnf",
f"""sudo bash -c 'cat >> /etc/mysql/mysql.conf.d/mysqld.cnf <<EOF
server-id={count}
log_bin=/var/log/mysql/mysql-bin.log
binlog_do_db=sakila
EOF'
""",
        "sudo systemctl restart mysql",
        # Create users for each replica
        f"sudo mysql -u root -prootpass -e \"CREATE USER 'repl'@'{replica_ips[0]}' IDENTIFIED WITH mysql_native_password BY 'replpass';\"",
        f"sudo mysql -u root -prootpass -e \"GRANT REPLICATION SLAVE ON *.* TO 'repl'@'{replica_ips[0]}';\"",
        f"sudo mysql -u root -prootpass -e \"CREATE USER 'repl'@'{replica_ips[1]}' IDENTIFIED WITH mysql_native_password BY 'replpass';\"",
        f"sudo mysql -u root -prootpass -e \"GRANT REPLICATION SLAVE ON *.* TO 'repl'@'{replica_ips[1]}';\"",
        "sudo mysql -u root -prootpass -e 'FLUSH PRIVILEGES;'",
        "sudo mysql -u root -prootpass -e 'exit'"
      ]
      run_ssh_commands(instance['public_ip'], commands)    
      log_file, log_pos = get_binary_log_coords(instance['public_ip'])
    else:
      commands = [
f"""sudo bash -c 'cat >> /etc/mysql/mysql.conf.d/mysqld.cnf <<EOF
server-id={count}
log_bin=/var/log/mysql/mysql-bin.log
binlog_do_db=sakila
relay-log=/var/log/mysql/mysql-relay-bin.log
EOF'
""",
        "sudo systemctl restart mysql",
        "sudo mysql -u root -prootpass -e 'STOP REPLICA;'",
        f"sudo mysql -u root -prootpass -e \"CHANGE REPLICATION SOURCE TO SOURCE_HOST='{source_ip[0]}', SOURCE_USER='repl', SOURCE_PASSWORD='replpass', SOURCE_LOG_FILE='{log_file}', SOURCE_LOG_POS={log_pos};\"",
        "sudo mysql -u root -prootpass -e 'START REPLICA;'",
        "sudo mysql -u root -prootpass -e 'exit'"
      ]
      run_ssh_commands(instance['public_ip'], commands)    
  
    count += 1


def run_flask_server(ip='', filename='', env_variables=''):
  upload_files_to_instance(ip=ip, files=[filename])
  without_ext = filename.split('.')[0]
  commands = [
    "sudo apt update -y",
    "sudo apt install python3.12-venv -y",
    "cd ~ && python3 -m venv venv",
    "cd ~ && source venv/bin/activate && pip install requests pymysql flask",
    f"cd ~ && nohup sudo {env_variables} ./venv/bin/python {filename} > {without_ext}.log 2>&1 & echo $! > {without_ext}.pid"
  ]
  run_ssh_commands(ip, commands)


def terminate_instance(instance_id):
  """
  Terminate one or multiple EC2 instances and display state transitions.
  
  Args:
    instance_id (list): List of instance IDs (strings) to terminate
  
  Returns:
    bool: True if termination request was successful, False if error occurred
  """
  instance_ids = instance_id if isinstance(instance_id, list) else [instance_id]
  try:
    response = ec2.terminate_instances(InstanceIds=instance_ids)
    
    print(f"Stopping instance {instance_id}...")
    
    # Check that the state is changing
    for instance in response['TerminatingInstances']:
      current_state = instance['CurrentState']['Name']
      previous_state = instance['PreviousState']['Name']
      print(f"   State: {previous_state} → {current_state}")
  
    return True
    
  except ClientError as e:
    print(f"Error during stopping : {e}")
    return False
