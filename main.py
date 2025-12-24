import boto3
import logging

from manage_instances import launch_instance


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),              # print to console
        logging.FileHandler("lab_demo.log")   # save to file
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
  manager_script = read_script('./user_data/manager_mysql_setup.sh')
  manager = launch_instance(instance_name='manager', type='t2.micro', user_data=manager_script)

  logger.info('[STEP 2] Launching worker instances')
  worker_script = read_script('./user_data/worker_mysql_setup.sh')
  worker_script = worker_script.replace("__MANAGER_IP__", manager.private_ip_address)
  worker1 = launch_instance(instance_name="worker-1", type='t2.micro', user_data=worker_script)
  worker2 = launch_instance(instance_name="worker-2", type='t2.micro', user_data=worker_script)


if __name__ == '__main__':
  main()
