# sudo systemctl start redis
clear
mkdir -p .flask_session
chmod 700 .flask_session

source venv/bin/activate

python prepMe.py


deactivate