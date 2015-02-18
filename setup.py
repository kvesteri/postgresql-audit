"""
PostgreSQL-Audit
----------------

Versioning and auditing extension for PostgreSQL and SQLAlchemy.
"""

import os
import re
from setuptools import find_packages, setup


HERE = os.path.dirname(os.path.abspath(__file__))


def get_version():
    filename = os.path.join(HERE, 'postgresql_audit', '__init__.py')
    with open(filename) as f:
        contents = f.read()
    pattern = r"^__version__ = '(.*?)'$"
    return re.search(pattern, contents, re.MULTILINE).group(1)


extras_require = {
    'test': [
        'flexmock==0.9.7',
        'pytest>=2.3.5',
        'psycopg2>=2.4.6',
    ],
}


# Add all optional dependencies to testing requirements.
for name, requirements in extras_require.items():
    if name != 'test':
        extras_require['test'] += requirements


setup(
    name='PostgreSQL-Audit',
    version=get_version(),
    url='https://github.com/kvesteri/postgresql-audit',
    license='BSD',
    author='Konsta Vesterinen',
    author_email='konsta@fastmonkeys.com',
    description=(
        'Versioning and auditing extension for PostgreSQL and SQLAlchemy.'
    ),
    packages=find_packages('.', exclude=['tests', 'tests.*']),
    long_description=__doc__,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=['SQLAlchemy>=0.9.4'],
    extras_require=extras_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
