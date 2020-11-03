# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://atlas.hashicorp.com/search.
  config.vm.box = "sagepe/stretch"

  config.vm.synced_folder ".", "/vagrant/caps/"

  # Speed up DNS lookups
  config.vm.provider "virtualbox" do |vb|
    vb.customize ["modifyvm", :id, "--natdnsproxy1", "off"]
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "off"]
  end


  # NFS requires a host-only network
  # This also allows you to test via other devices (e.g. mobiles) on the same
  # network
  config.vm.network :private_network, ip: "10.11.12.13"

  # Django dev server
  config.vm.network "forwarded_port", guest: 8000, host: 8000
  # Solr server
  config.vm.network "forwarded_port", guest: 8983, host: 8983

  # Give the VM a bit more power to speed things up
  config.vm.provider "virtualbox" do |v|
    v.memory = 2048
    v.cpus = 1
  end

  # Provision the vagrant box
  config.vm.provision "shell", path: "conf/provisioner.sh", privileged: false
  config.vm.provision "shell", inline: <<-SHELL
	sudo apt update

    cd /vagrant/caps

    #fix dpkg-preconfigure error
    export DEBIAN_FRONTEND=noninteractive

    # Install the packages from conf/packages
    xargs sudo apt-get install -qq -y < conf/packages
	xargs sudo apt-get install -qq -y < conf/dev_packages
    # Install some of the other things we need that are just for dev
    sudo apt-get install -qq -y ruby-dev libsqlite3-dev build-essential

    # Create a postgresql user
    sudo -u postgres psql -c "CREATE USER caps SUPERUSER CREATEDB PASSWORD 'caps'"
    # Create a database
    sudo -u postgres psql -c "CREATE DATABASE caps"

    # Get Solr
    cd /vagrant
    curl -LO https://archive.apache.org/dist/lucene/solr/6.6.0/solr-6.6.0.tgz

    # Unpack it
    mkdir solr
    tar -C solr -xf solr-6.6.0.tgz --strip-components=1
    cd /vagrant/caps

    # Run post-deploy actions script to update the virtualenv, install the
    # python packages we need, migrate the db and generate the sass etc
    conf/post_deploy_actions.bash

    # Create a superuser
    script/console -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@example.com', 'password')"

	# give permissions to vagrant user on all the packages
	sudo chmod -R ugo+rwx /vagrant
  SHELL

end
