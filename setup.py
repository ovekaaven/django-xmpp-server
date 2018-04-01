# -*- coding=utf-8 -*-
import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-xmpp-server',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    license='MIT License',
    description='XMPP Server for Django',
    long_description=README,
    url='https://github.com/ovekaaven/django-xmpp-server',
    author='Ove Kåven',
    author_email='post@ovekaaven.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Communications :: Chat',
        'Topic :: Communications :: Conferencing',
        'Topic :: Internet :: XMPP',
    ],
    keywords='xmpp',
    install_requires=[
        'Django', 'channels', 'slixmpp', 'defusedxml'
    ],
    extras_require={
        'tcp': ['Twisted', 'pyOpenSSL'],
    },
)
