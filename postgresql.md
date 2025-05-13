az postgres flexible-server db list --server-name azpostgreserver --resource-group rg-flowerapp

psql "host=<your-db-host> port=<your-db-port> dbname=<your-db-name> user=<your-db-user> password=<your-db-password> sslmode=require" -f create_flowers_table.sql

psql "host=azpostgreserver.postgres.database.azure.com port=5432 dbname=azdb user=myadmin password=@Azadeh2025@ sslmode=require" -f create_flowers_table.sql