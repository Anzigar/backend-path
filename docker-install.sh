#!/bin/bash

echo "Docker Installation Script"
echo "=========================="

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "Detected macOS system"
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        echo "Homebrew already installed. Updating..."
        brew update
    fi
    
    # Install Docker Desktop for Mac
    if ! command -v docker &> /dev/null; then
        echo "Installing Docker Desktop for Mac..."
        brew install --cask docker
        echo "Docker Desktop installed. Please start Docker Desktop application."
    else
        echo "Docker already installed."
    fi
    
    # Install Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "Installing Docker Compose..."
        brew install docker-compose
    else
        echo "Docker Compose already installed."
    fi

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "Detected Linux system"
    
    # Check if user has sudo access
    if ! command -v sudo &> /dev/null; then
        echo "Error: sudo command not found. Please run this script with a user that has sudo privileges."
        exit 1
    fi
    
    # Update package index
    echo "Updating package index..."
    sudo apt-get update
    
    # Install prerequisites
    echo "Installing prerequisites..."
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    echo "Adding Docker's GPG key..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Set up the Docker repository
    echo "Setting up Docker repository..."
    echo \
      "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    echo "Installing Docker Engine..."
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Add current user to the docker group to use Docker without sudo
    sudo usermod -aG docker $USER
    
    # Install Docker Compose
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.18.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo "Docker installation complete. You may need to log out and log back in for group changes to take effect."

else
    echo "Unsupported OS: $OSTYPE"
    echo "Please install Docker manually from https://docs.docker.com/get-docker/"
    exit 1
fi

echo "Docker installation completed."
echo "You can verify the installation by running: docker --version"
