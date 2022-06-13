# Devcontainer choices

# Default

This will build a container using the image pre-built by `.github/workflows/create_docker.yml`, and bootstrap a full database from the [caps_data](https://github.com/mysociety/caps_data) repo.

# No initial populate

This will build a container using the image pre-built by `.github/workflows/build_dev_container.yml`, but not run any database creation commands. You'll need to run `script/setup-in-docker` to populate. 

# No cached docker image

This will build a container using the instructions in `Dockerfile`. This will take longer, but might be useful in reviewing changes that affect the dockerfile (and so will not be reflected in the current image).