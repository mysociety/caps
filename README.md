# caps

# Install

Clone the repository

```
git clone git@github.com:crowbot/caps.git
cd caps
```

A Vagrantfile is included for local development. Assuming you have [Vagrant](https://www.vagrantup.com/) installed, you can create a Vagrant VM with:

```
vagrant up
```

Then SSH into the VM, and run the server script:

```
vagrant ssh
script/server
```

The site will be visible at <http://localhost:8001>.

# Publish

```
script/publish
