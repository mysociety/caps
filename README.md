# caps - Climate Action Plans

# Development Install

Clone the repository

```
git clone git@github.com:mysociety/caps.git
cd caps
script/bootstrap
```

You then have two options for a local development environment, [Vagrant](https://www.vagrantup.com/) and [Docker](https://www.docker.com/products/docker-desktop). These instructions don't cover installing and setting up these tools.

This application makes calls to [MapIt](https://mapit.mysociety.org). If you plan on making more than 50 calls a day, you'll [need an API key](https://mapit.mysociety.org/pricing/).

## Loading Data

The first time you stand-up a local development environment, you'll need to pull down the Council, plans and emissions data and import this into the database and search index. The instructions below provide details on how to do this for each environment.

This process can take some time, and a slightly faster update process is also available.

## Docker

This project contains a Docker Compose file that uses the Django development server, enables debug mode and maps the local working copy into the container for testing.

If you are using a MapIt API key, add this to your `.env` file, e.g.: `echo 'MAPIT_API_KEY=xxxaaa111222333zzz' >> .env`.

### Using the setup script

*Warning* running `script/setup` will remove all locally cached data and reset the environment to the default state!

Having rest the environment, `script/setup` will perform all the necessary setup steps, including loading all data. Once this has completed, you should have a functional environment.

This may take a long time to run!

### Manual setup

Run `docker-compose up`. This will build an application container and stand-up this, together with PostgreSQL and Solr containers. These will run in the foreground, so you will see console output in the shell from the containers. You can stop the containers by hitting `control-C`. If you'd rather run in the background, add the `-d` switch; if you do this you can stop the environment with `docker-compose down`.

You can then run `docker-compose exec app script/update --all` to perform the initial data load. This will take a long time. Run the same command without the `--all` switch to run the short-cut data load.

You can rebuild the application container by running `script/build`. Bear in mind that when running the container in development mode, your local working copy will be included along with any local uncommitted changes.

The environment will be visible at http://localhost:8000 and the Solr admin interface at http://localhost:8983

## Vagrant

Copy across some basic config. You may need to add a MapIt API key.

```
cp conf/config.py-example conf/config.py
```

A functional Vagrantfile is included for local development so you can create a Vagrant VM with:

```
vagrant up
```

Then SSH into the VM, and run subsequent commands from inside.

```
vagrant ssh
```

### Importing data

Before running the development server for the first time, you'll need to import the data and set up the search index:

```
script/update --all
```

This process will take some time. Once you have done a full import, you can subsequently run `script/update` to take a few shortcuts in future.

### Starting the development server

Then you can start the development server:

```
script/server
```

The site will be visible at <http://localhost:8000>.

The Solr server interface will be visible at <http://localhost:8983>
