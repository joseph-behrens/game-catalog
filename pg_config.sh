apt-get -qqy update
DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
apt-get -qqy install python-sqlalchemy
apt-get -qqy install python-pip
pip install --upgrade pip
pip install werkzeug
pip install flask
pip install Flask-Login
pip install oauth2client
pip install requests
pip install httplib2
