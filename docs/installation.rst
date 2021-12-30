Installation
============

.. include:: ../README.rst
   :end-before: For more documentation on Pywikibot

Settings
--------

It is recommended to create a `user-config.py` file if Pywikibot is used as a
site package. If Pywikibot is used in directory mode e.g. from a repository
the configuration file is mandatory. A minimal sample is shown below.

.. literalinclude:: ../user-config.py.sample

This sample is shipped with the repository but is not available with
the site-package. For more settings use
:mod:`generate_user_files<pywikibot.scripts.generate_user_files>` script
or refer :py:mod:`pywikibot.config` module.

.. note::
   Please also see the documentation at :manpage:`Installation`
