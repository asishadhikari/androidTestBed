#get the required tools to use the repositories over https
sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

#add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

#setup apt to use stable repo for docker
sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
sudo apt update

#install the latest docker version community engine and containerd
sudo apt-get install docker-ce docker-ce-cli containerd.io

#post installation configurations to allow docker to be run as non sudoer

sudo groupadd docker

sudo usermod -aG docker $USER

#get docker images for client and server containers
docker pull renanalves/android-testbed
docker pull renanalves/server-testbed
docker pull nginx
#get the required python packages
pip3 install -r requirements.txt

