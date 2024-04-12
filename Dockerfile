##
## Dockerfile to generate a Docker image from a Django project
##
# Start from an existing image with Miniconda installed
FROM continuumio/miniconda3
MAINTAINER OrinMcD
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE=atai_project.settings
ENV DOCKER_ENV=True

# Install necessary packages including cron
RUN apt-get update && \
    apt-get install -y cron sudo nano && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Update Conda
RUN conda update -n base conda && conda update -n base --all

# Make a working directory in the image and set it as working dir.
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Copy the environment.yml file and create the Conda environment
COPY ENV.yml /usr/src/app
RUN conda env create -n atai_project --file ENV.yml

# Activate the Conda environment
RUN echo "conda activate atai_project" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

# Install uwsgi
RUN conda install uwsgi

# Create the static directory
RUN mkdir -p /usr/src/app/static

# Copy the project files to the container
COPY . /usr/src/app

# Collect static files
RUN python manage.py collectstatic --no-input

# Expose the port uwsgi will listen on
EXPOSE 8001

# Add your cron file to the cron directory
COPY django_cronjobs /etc/cron.d/django_cronjobs

# Give execution rights on the cron job and apply it
RUN chmod 0644 /etc/cron.d/django_cronjobs && \
    crontab /etc/cron.d/django_cronjobs && \
    touch /var/log/cron.log

# Run cron and uwsgi when the container starts
CMD cron && uwsgi --ini uwsgi.ini
