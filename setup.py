from setuptools import find_packages, setup

setup(
    name="django-manticoresearch",
    version="0.3.1",
    packages=find_packages(),
    install_requires=[
        "django>=3.2",
        "manticoresearch>=3.0.0",
        "ndjson>=0.3.1",
    ],
    author="michael7nightingale",
    author_email="suslanchikmopl@gmail.com",
    description="Django integration for Manticore Search",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/michael7nightingale/django-manticoresearch",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    python_requires=">=3.6",
)
