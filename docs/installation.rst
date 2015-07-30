Installation
============

This part of the documentation covers the installation of PostgreSQL-Audit.

Supported platforms
-------------------

PostgreSQL-Audit has been tested against the following Python platforms.

- cPython 2.7
- cPython 3.3
- cPython 3.4
- cPython 3.5


Installing an official release
------------------------------

You can install the most recent official PostgreSQL-Audit version using
pip_::

    pip install postgresql-audit

.. _pip: http://www.pip-installer.org/

Installing the development version
----------------------------------

To install the latest version of PostgreSQL-Audit, you need first obtain a
copy of the source. You can do that by cloning the git_ repository::

    git clone git://github.com/kvesteri/postgresql-audit.git

Then you can install the source distribution using the ``setup.py``
script::

    cd postgresql-audit
    python setup.py install

.. _git: http://git-scm.org/

Checking the installation
-------------------------

To check that PostgreSQL-Audit has been properly installed, type ``python``
from your shell. Then at the Python prompt, try to import PostgreSQL-Audit,
and check the installed version:

.. parsed-literal::

    >>> import postgresql_audit
    >>> postgresql_audit.__version__
    |release|
