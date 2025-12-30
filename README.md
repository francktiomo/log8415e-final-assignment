# log8415e Final Project

## Instructions to run the code

Make sure to be at the root of the project and follow these steps:

1. Provide the credentials <br>

   - Make sure to copy your `aws_access_key_id` and `aws_secret_access_key` and paste them into `~/.aws/credentials`.
   - Also make sure to download a user ssh key from AWS, rename it to `lab8415-final.pem` or any other name you like and add it to the root project directory.

2. Create a virtual environment <br>
   Execute this command to create a new virtual environment: `python -m venv venv` and active it using `venv\Scripts\Activate.ps1` if on Windows PowerShell or `source venv/bin/activate` if on Linux/Mac.

3. Install dependencies <br>
   Run `pip install -r requirements.txt`

4. Run de script <br>
   To run the script, execute the following command: `python main.py`
