# DB Backup Tool

Narzędzie do backupu baz danych MySQL/MariaDB z interfejsem WWW. Wspiera zarówno bezpośrednie połączenia TCP/IP jak i tunelowanie przez SSH.

## Funkcje

- Zarządzanie serwerami baz danych
- Testowanie połączeń
- Tworzenie backup'ów baz danych
- Harmonogramowanie zadań backup'u
- Historia wykonanych operacji

## Wymagania

- Python 3.8+
- Django 5.2+
- MySQL/MariaDB lub klient
- Dostęp do serwerów baz danych

## Instalacja

1. Sklonuj repozytorium:
   ```
   git clone https://github.com/twojlogin/db-backup-tool.git
   cd db-backup-tool
   ```

2. Utwórz wirtualne środowisko i zainstaluj zależności:
   ```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

3. Utwórz plik .env na podstawie .env.example i dostosuj:
   ```
   cp .env.example .env
   # Edytuj plik .env z odpowiednimi wartościami
   ```

4. Wykonaj migracje bazy danych:
   ```
   python manage.py migrate
   ```

5. Uruchom serwer deweloperski:
   ```
   python manage.py runserver
   ```

6. Przejdź do http://127.0.0.1:8000 w przeglądarce

## Konfiguracja

Wszystkie wrażliwe ustawienia przechowywane są w pliku `.env`. Upewnij się, że ten plik nie jest umieszczany w publicznym repozytorium.

## Licencja

[MIT License](LICENSE)