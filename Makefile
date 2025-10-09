manage = cd testproject && DJANGO_SETTINGS_MODULE=testproject.settings python3 manage.py

tests:
	$(manage) test --verbosity=2

linter:
	pylint --py-version=3.10 --disable=R,C,W ./django_manticoresearch

build:
	python3 -m build

tox:
	tox
