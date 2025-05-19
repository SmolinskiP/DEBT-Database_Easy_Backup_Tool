from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import getpass
import sys


class Command(BaseCommand):
    help = 'Tworzy użytkownika aplikacji'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Nazwa użytkownika')
        parser.add_argument('--email', type=str, help='Adres email')
        parser.add_argument('--admin', action='store_true', help='Czy użytkownik ma być administratorem')

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email', '')
        is_admin = options.get('admin', False)
        
        # Sprawdź czy użytkownik już istnieje
        if User.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f'Użytkownik "{username}" już istnieje'))
            return
            
        # Pobierz hasło (2 razy dla potwierdzenia)
        password = getpass.getpass('Hasło: ')
        password_confirm = getpass.getpass('Potwierdź hasło: ')
        
        if password != password_confirm:
            self.stderr.write(self.style.ERROR('Hasła nie pasują do siebie'))
            return
            
        if len(password) < 8:
            self.stderr.write(self.style.ERROR('Hasło musi mieć co najmniej 8 znaków'))
            return
            
        # Utwórz użytkownika
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=is_admin,
            is_superuser=is_admin
        )
        
        self.stdout.write(self.style.SUCCESS(f'Użytkownik "{username}" został utworzony pomyślnie'))
        if is_admin:
            self.stdout.write(self.style.SUCCESS('Użytkownik ma uprawnienia administratora'))