# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://atlas.hashicorp.com/search.
  config.vm.box = "sagepe/buster"
  config.vm.box_version = ">= 2.0.0 , < 3.0"

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
    cd /vagrant/caps

    # fix dpkg-preconfigure error
    export DEBIAN_FRONTEND=noninteractive

    # Add Java Repo
    wget -qO - https://adoptopenjdk.jfrog.io/adoptopenjdk/api/gpg/key/public | apt-key add -
    echo 'deb https://adoptopenjdk.jfrog.io/adoptopenjdk/deb/ buster main' > /etc/apt/sources.list.d/adoptopenjdk.list

    # Update Apt
    apt-get -qq update

    # Install the packages from conf/packages
    xargs apt-get install -qq < conf/packages

    # Install some of the other things we need that are just for dev
    xargs apt-get install -qq < conf/dev_packages

    # Create a postgresql user
    sudo -u postgres psql -c "CREATE USER caps SUPERUSER CREATEDB PASSWORD 'caps'"

    # Create a database
    sudo -u postgres psql -c "CREATE DATABASE caps"

    # Get Solr
    cd /vagrant
    curl --silent -LO https://archive.apache.org/dist/lucene/solr/6.6.0/solr-6.6.0.tgz

    # Install it as non-root user
    tar xzf solr-6.6.0.tgz solr-6.6.0/bin/install_solr_service.sh --strip-components=2
    ./install_solr_service.sh solr-6.6.0.tgz

    # Create caps
    su solr -c '/opt/solr/bin/solr create -c caps -n basic_config'
    ln -sf /vagrant/caps/conf/schema.xml /var/solr/data/caps/conf/schema.xml
    ln -sf /vagrant/caps/conf/solrconfig.xml /var/solr/data/caps/conf/solrconfig.xml
    /bin/systemctl restart solr

    cd /vagrant/caps

    # Use a new, upstream version of Pip
    curl -L -s https://bootstrap.pypa.io/get-pip.py | python3

    # Run bootstrap script to install the python packages we need
    # Then migrate the db, generate the sass, etc
    script/bootstrap

    # Create a superuser
    script/console -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@example.com', 'password')"

  SHELL

end
