git pull &&
  mv -f /var/www/html/ptools/start.sh /var/www/html/start.sh &&
  python manage.py makemigrations &&
  python manage.py migrate
