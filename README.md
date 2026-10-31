# Pocket RPG (Kivy)

Текстовая RPG для Android: 3 класса, прокачка, пошаговые бои с инициативой, критами, ядом и оглушением, квест, магазин, таверна и автосохранение.

## Файлы

- `main.py`: интерфейс на Kivy
- `engine.py`: игровая логика (без Kivy)
- `tests/test_engine.py`: тесты логики
- `buildozer.spec`: настройки сборки APK
- `.github/workflows/build-apk.yml`: сборка APK на GitHub

## Сборка APK только с телефона (через GitHub Actions)

Buildozer внутри Termux нормально не работает, поэтому APK собирает GitHub на своём сервере.

1. Создай пустой репозиторий на github.com, например `pocket-rpg`.
2. В Termux:

```bash
pkg install git unzip gh
termux-setup-storage
unzip ~/storage/downloads/pocket_rpg_kivy.zip -d ~
cd ~/pocket_rpg
gh auth login
git init
git add .
git commit -m "Pocket RPG"
git branch -M main
git remote add origin https://github.com/ТВОЙ_НИК/pocket-rpg.git
git push -u origin main
```

3. На GitHub открой **Actions**, затем **Build APK**. Первая сборка идёт 20-40 минут.
4. Скачай артефакт `pocket-rpg-apk`, распакуй zip и установи APK (разреши установку из неизвестных источников).

## Проверка логики в Termux

```bash
cd ~/pocket_rpg
python -m unittest discover -s tests -v
```

Сохранение хранится во внутренней папке приложения, разрешения на память не нужны.
