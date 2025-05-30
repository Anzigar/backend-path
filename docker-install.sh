#!/bin/bash

# Exit on error
set -e

echo "Checking for and removing old Docker versions..."
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y $pkg 2>/dev/null || true
done

echo "Updating package list..."
sudo apt-get update

echo "Installing required dependencies..."
sudo apt-get install -y ca-certificates curl

# Download and add Docker's official GPG key:
echo "Adding Docker GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

echo "Installing Docker Engine, CLI, and containerd..."
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

echo "Adding current user to the Docker group..."
# Create the docker group if it doesn't exist
sudo groupadd docker 2>/dev/null || echo "docker group already exists"
sudo usermod -aG docker $USER

# Fix permissions if ~/.docker directory exists
if [ -d "$HOME/.docker" ]; then
  echo "Fixing Docker directory permissions..."
  sudo chown "$USER":"$USER" "$HOME/.docker" -R
  sudo chmod g+rwx "$HOME/.docker" -R
fi

echo "Starting and enabling Docker service..."
sudo systemctl enable docker.service
sudo systemctl enable containerd.service
sudo systemctl start docker.service

echo "Verifying Docker installation..."
docker run --rm hello-world || {
  echo "Docker test failed. You may need to log out and back in for group changes to take effect."
  echo "Alternatively, you can run: newgrp docker"
}

echo "Installation complete! Run 'docker --version' to check the installation."
echo "NOTE: You may need to log out and log back in for user group changes to take effect."
echo "If you don't want to log out now, you can run 'newgrp docker' to activate changes for this session."
