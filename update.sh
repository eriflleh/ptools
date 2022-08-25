git pull &&
  mv -f ./start.sh ../start.sh &&
  python manage.py makemigrations &&
  python manage.py migrate
