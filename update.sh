git pull https://gitee.com/ngfchl/ptools &&
  python manage.py makemigrations &&
  python manage.py migrate &&
  python manage.py loaddata db/pt.json

