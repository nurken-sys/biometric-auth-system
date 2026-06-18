Тұлғаның биометриялық мәліметтері негізінде аутентификация жүйесін әзірлеу

Бұл репозиторий дипломдық жұмыс аясында әзірленген бағдарламалық кешеннің бастапқы коды мен конфигурациялық файлдарын қамтиды. Жүйе пайдаланушыларды бет-әлпеті және дауысы (дауыс таңбасы) арқылы екі факторлы биометриялық сәйкестендіруді жүзеге асыруға, сондай-ақ қауіпсіз авторизациялауға арналған.

Технологиялар стегі

Бағдарламалау тілі: Python 3.x

Web-фреймворк: Django

Веб-сервер және прокси: Nginx, Gunicorn

Мәліметтер базасы: SQLite (әзірлеу үшін) / PostgreSQL (өндірістік орта үшін)

Компьютерлік көру және аудио өңдеу: Face-API (бет-әлпетті тану), VOSK (дауысты тану)

Қауіпсіздік және желі: HTTPS, Ngrok (қауіпсіз туннельдеу)

Негізгі мүмкіндіктері

Пайдаланушыларды жүйеге тіркеу және биометриялық деректерін (бет-әлпет шаблоны, дауыс үлгісі) сақтау.

Бет-әлпет арқылы нақты уақыт режимінде (real-time) биометриялық тану.

Дауыс және арнайы фразалар арқылы тану (VOSK кітапханасы негізінде).

Жүйедегі барлық кіру/шығу әрекеттерін мәліметтер базасына тіркеу.

Ортаны дайындау және іске қосу нұсқаулығы

Жүйені өндірістік ортада (Ubuntu Linux сервері) немесе жергілікті компьютерде орнату үшін төмендегі қадамдарды қатаң сақтау қажет.

1. Жобаны жүктеп алу және тәуелділіктерді орнату

Сервердің терминалында репозиторийді клондаңыз және жоба бумасына өтіңіз:

git clone https://github.com/nurken-sys/biometric-auth-system.git
cd biometric-auth-system


Виртуалды ортаны құрып, оны іске қосыңыз:

python3 -m venv .venv
source .venv/bin/activate


Жобаның жұмысына қажетті барлық кітапханаларды орнатыңыз:

pip install -r requirements.txt


2. Жобаны баптау

Мәліметтер базасының құрылымын жасау үшін миграцияларды орындаңыз:

python manage.py migrate


Nginx веб-сервері дұрыс жұмыс істеуі үшін барлық статикалық файлдарды (CSS, JS, суреттер) бір ортақ каталогқа жинаңыз:

python manage.py collectstatic


3. Gunicorn серверін баптау (Бэкенд)

Django жобасын тұрақты фондық режимде іске қосу үшін Systemd қызметін құру қажет.

Қызмет файлын ашыңыз:

sudo nano /etc/systemd/system/biometric.service


Төмендегі конфигурацияны енгізіңіз (жолдарды өз жүйеңізге сәйкестендіріңіз):

[Unit]
Description=Gunicorn daemon for Biometric Auth System
After=network.target

[Service]
User=nurken
Group=www-data
WorkingDirectory=/home/nurken/biometric-auth-system
ExecStart=/home/nurken/biometric-auth-system/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 config.wsgi:application

[Install]
WantedBy=multi-user.target


Қызметті іске қосыңыз:

sudo systemctl start biometric
sudo systemctl enable biometric


4. Nginx веб-серверін баптау (Фронтенд және Статика)

Nginx сервері клиенттерден келетін сұраныстарды қабылдап, статикалық файлдарды таратады.

Конфигурация файлын ашыңыз:

sudo nano /etc/nginx/sites-available/biometric


Төмендегі баптауларды енгізіңіз:

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /home/nurken/biometric-auth-system/staticfiles/;
    }

    location /media/ {
        alias /home/nurken/biometric-auth-system/uploads/;
    }
}


Конфигурацияны іске қосыңыз:

sudo ln -s /etc/nginx/sites-available/biometric /etc/nginx/sites-enabled
sudo systemctl restart nginx


5. HTTPS және қауіпсіздік (Ngrok арқылы)

Заманауи браузерлердің қауіпсіздік саясатына сәйкес (камера мен микрофонға рұқсат алу үшін), жүйе міндетті түрде HTTPS хаттамасы арқылы жұмыс істеуі тиіс. Бұл мәселені шешу үшін Ngrok туннельдеу жүйесі қолданылады.

Ngrok орнату және іске қосу:

sudo snap install ngrok
ngrok config add-authtoken <СІЗДІҢ_ТОКЕНІҢІЗ>
ngrok http 80


Іске қосылғаннан кейін терминалда https://[кездейсоқ-атау].ngrok-free.app форматындағы сілтеме пайда болады. Осы сілтеме арқылы жүйеге кез келген құрылғыдан (смартфон, дербес компьютер) қауіпсіз кіруге және биометриялық сенсорларды толыққанды пайдалануға болады.
