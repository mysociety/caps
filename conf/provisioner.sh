if ! grep -q "cd /vagrant" ~/.bashrc ; then
    echo "cd /vagrant/caps" >> ~/.bashrc
fi
