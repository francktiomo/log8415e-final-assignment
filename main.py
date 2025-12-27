import boto3
import logging

from manage_instances import *


# Configure logging
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
  handlers=[
    logging.StreamHandler(),
    logging.FileHandler("lab_demo.log")
  ]
)
logger = logging.getLogger(__name__)


def read_script(path):
  with open(path) as f:
    return f.read()

def main():
  ec2 = boto3.client('ec2', region_name='us-east-1')
  logger.info('========== AWS EC2 AUTOMATION SCRIPT STARTED ==========')

  logger.info('[STEP 1] Launching manager instance')
  sakila_script = read_script('./user_data/sakila_install.sh')
  manager = launch_instance(instance_name='manager', type='t2.micro', user_data=sakila_script)

  logger.info('[STEP 2] Launching worker instances')
  worker1 = launch_instance(instance_name="worker-1", type='t2.micro', user_data=sakila_script)
  worker2 = launch_instance(instance_name="worker-2", type='t2.micro', user_data=sakila_script)
  
  logger.info('[STEP 3] Check Sakila installation on instances')
  instances = [manager, worker1, worker2]
  check_sakila_installation(instances)

  logger.info('[STEP 4] Configure manager and workers for replication')
  configure_db_for_replication(instances)

  logger.info('[STEP 5] Setup proxy')
  proxy_user_data = """#!/bin/bash
  sudo apt update
  sudo apt install python3-pip -y
  pip3 install flask pymysql"""
  proxy = launch_instance(instance_name='proxy', type='t2.large', user_data=proxy_user_data)
  instances.append(proxy)
  run_flask_server(
    ip=proxy['public_ip'],
    filename='proxy.py',
    env_variables=f"MANAGER_IP={manager['private_ip']} WORKERS_IPS='{worker1['private_ip']},{worker2['private_ip']}' MODE='custom'"
  )
  
  logger.info('[STEP 6] Setup Gatekeeper')
  gatekeeper_user_data = """#!/bin/bash
  sudo apt update
  sudo apt install python3-pip -y
  pip3 install flask requests"""
  gatekeeper = launch_instance(instance_name='gatekeeper', type='t2.large', user_data=gatekeeper_user_data)
  instances.append(gatekeeper)
  run_flask_server(
    ip=gatekeeper['public_ip'],
    filename='gatekeeper.py',
    env_variables=f"PROXY_URL=http://{proxy['private_ip']}:5000/proxy API_KEY=secret123"
  )

  logger.info('[STEP 6] Stop Instances')
  for instance in instances:
    terminate_instance(instance['instance_id'])
  

if __name__ == '__main__':
  main()
