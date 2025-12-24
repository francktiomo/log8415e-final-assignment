import boto3

from botocore.exceptions import ClientError

UBUNTU_AMI = 'ami-0ecb62995f68bb549'
ec2 = boto3.resource('ec2')
client = boto3.client('ec2')

def ensure_ports_open(ec2, sg_id, ports):
  """
  Ensure that all given ports are open in the specified security group.
  Args:
    ec2 (boto3.client): EC2 client instance for AWS operations
    sg_id (str): Id of the security group to modify
    ports (list[int]): Ports which needs to be opened
  """
  try:
    sg_info = client.describe_security_groups(GroupIds=[sg_id])["SecurityGroups"][0]
    existing_permissions = sg_info.get("IpPermissions", [])
    existing_ports = [p.get("FromPort") for p in existing_permissions if "FromPort" in p]

    for port in ports:
      if port not in existing_ports:
        try:
          client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
              "IpProtocol": "tcp",
              "FromPort": port,
              "ToPort": port,
              "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            }]
          )
          print(f"Added inbound rule for port {port} to SG {sg_id}")
        except client.exceptions.ClientError as e:
          if "InvalidPermission.Duplicate" in str(e):
            pass
          else:
            raise
      else:
        print(f"Port {port} already opened in SG {sg_id}")
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
  vpcs = client.describe_vpcs(Filters=[{'Name': 'is-default', 'Values': ['true']}])
  default_vpc_id = vpcs['Vpcs'][0]['VpcId']

  # Get the first of the default VPC
  subnets = client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}])
  default_subnet_id = subnets['Subnets'][0]['SubnetId']
  
  # Get the default security group
  security_groups = client.describe_security_groups(
    Filters=[
      {'Name': 'vpc-id', 'Values': [default_vpc_id]},
      {'Name': 'group-name', 'Values': ['default']}
    ]
  )
  default_sg_id = security_groups['SecurityGroups'][0]['GroupId']

  # Open all required ports
  ports_to_open = [22, 80, 3306, 5000]
  ensure_ports_open(client, default_sg_id, ports_to_open)
    
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
    instance = ec2.create_instances(
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
    )[0]

    print(f"Launching {instance_name}…")
    instance.wait_until_running()
    instance.reload()
    print(instance_name, instance.private_ip_address)

    return instance

  except ClientError as e:
    print(f"Error during launching: {e}")
    return None
