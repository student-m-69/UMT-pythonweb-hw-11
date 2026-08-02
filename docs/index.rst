Contacts API documentation
==========================

REST API for storing and managing contacts, built with FastAPI, SQLAlchemy,
PostgreSQL and Redis. Users register, verify their email and work with their
own contacts through JWT-protected routes.

.. toctree::
   :maxdepth: 2

Application
-----------

.. automodule:: main
   :members:
   :undoc-members:

Configuration
-------------

.. automodule:: src.conf.config
   :members:
   :undoc-members:

Database
--------

.. automodule:: src.database.db
   :members:
   :undoc-members:

.. automodule:: src.database.models
   :members:
   :undoc-members:
   :exclude-members: metadata, registry

Schemas
-------

.. automodule:: src.schemas
   :members:
   :undoc-members:

Repository
----------

.. automodule:: src.repository.contacts
   :members:
   :undoc-members:

.. automodule:: src.repository.users
   :members:
   :undoc-members:

Routes
------

.. automodule:: src.routes.auth
   :members:
   :undoc-members:

.. automodule:: src.routes.contacts
   :members:
   :undoc-members:

.. automodule:: src.routes.users
   :members:
   :undoc-members:

Services
--------

.. automodule:: src.services.auth
   :members:
   :undoc-members:

.. automodule:: src.services.cache
   :members:
   :undoc-members:

.. automodule:: src.services.email
   :members:
   :undoc-members:

.. automodule:: src.services.limiter
   :members:
   :undoc-members:

Indices
=======

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
