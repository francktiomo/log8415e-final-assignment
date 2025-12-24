#!/bin/bash
sudo apt update -y
sudo apt install mysql-server -y

sudo systemctl start mysql
sudo systemctl enable mysql

sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'rootpass'; FLUSH PRIVILEGES;"

# Install dependencies
sudo apt install sysbench wget unzip -y

wget https://downloads.mysql.com/docs/sakila-db.zip
unzip sakila-db.zip

sudo mysql -u root -prootpass < sakila-db/sakila-schema.sql
sudo mysql -u root -prootpass < sakila-db/sakila-data.sql
