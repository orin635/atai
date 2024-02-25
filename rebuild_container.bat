@echo off

REM Stop and remove the Docker container
docker stop atai_django
docker rm atai_django

REM Remove the Docker image
docker rmi atai_project:latest

REM Rebuild the Docker image
docker build -t atai_project .

REM Build the Docker container
docker create --name atai_django --network atai_network --network-alias atai_django -t -p 8001:8001 atai_project

REM Start the Docker container
docker start atai_django