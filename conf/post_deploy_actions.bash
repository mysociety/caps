#!/bin/bash

# abort on any errors
set -e

# check that we are in the expected directory
cd `dirname $0`/..

virtualenv_args=""
virtualenv_dir='../venv'
virtualenv_activate="$virtualenv_dir/bin/activate"
if [ ! -f "$virtualenv_activate" ]
then
    python3 -m venv $virtualenv_dir  --without-pip
fi
source $virtualenv_activate

# Upgrade pip to a secure version
curl -L -s https://bootstrap.pypa.io/get-pip.py | python3

pip3 install --requirement requirements.txt

# make sure that there is no old code (the .py files may have been git deleted)
find . -name '*.pyc' -delete

# get the database up to speed
python3 manage.py migrate

mkdir -p data/plans

curl -L -s https://raw.githubusercontent.com/ajparsons/uk_local_authority_names_and_codes/master/lookup_name_to_registry.csv > data/lookup_name_to_registry.csv

curl -L -s https://raw.githubusercontent.com/ajparsons/uk_local_authority_names_and_codes/master/uk_local_authorities.csv > data/uk_local_authorities.csv

curl -L -s http://geoportal1-ons.opendata.arcgis.com/datasets/43d30f924b29452b881e1820dcf897f9_0.csv > data/combined_authorities.csv

