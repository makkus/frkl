========
Overview
========


.. image:: https://img.shields.io/pypi/v/frkl.svg
           :target: https://pypi.python.org/pypi/frkl
           :alt: pypi

.. image:: https://readthedocs.org/projects/frkl/badge/?version=latest
           :target: https://frkl.readthedocs.io/en/latest/?badge=latest
           :alt: documentation

.. image:: https://gitlab.com/frkl/frkl/badges/develop/pipeline.svg
           :target: https://gitlab.com/frkl/frkl/pipelines
           :alt: pipeline status

.. image:: https://pyup.io/repos/github/makkus/frkl/shield.svg
           :target: https://pyup.io/repos/github/makkus/frkl/
           :alt: updates

.. image:: https://coveralls.io/repos/github/makkus/frkl/badge.svg?branch=develop
           :target: https://coveralls.io/github/makkus/frkl?branch=develop
           :alt: coveralls

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
           :target: https://github.com/ambv/black
           :alt: codestyle

*elastic configuration files*

*frkl* is basically a string/object transformation library, with the main goal being enabling as minimal as possible initial state. I rather suspect that this here is one of those things whose value won't be immediately obvious (if there is one at all -- still not sure about that myself), and examples might be a better way of explaining what its use is.

*frkl* is most useful for cases where you have a list of similar configuration items, which might or might not inherit from each other. In those cases, you don't want to duplicate information that is needed for each of the items. To illustrate, here's some yaml:

.. code-block:: yaml

   vars:
     location: at_home
     task_type: cleaning
   tasks:
     - clean_bathroom
     - clean_living_room
     - clean_desk:
         location: at_work

This task list describes how we want to clean three things, two of which are at home, and one is at work. Our robot would not like this way of describing it though, since it is much harder to parse. For example, there is no 'proper' schema, the list for example has mixed types, strings and a dictionary with one key/value pair. What our robot would want is:

.. code-block:: yaml

   - task:
       name: clean_bathroom
     vars:
       location: at_home
       task_type: cleaning
   - task:
       name: clean_living_room
     vars:
       location: at_home
       task_type: cleaning
   - task:
       name: clean_desk
     vars:
       location: at_work
       task_type: cleaning

Basically, this is what *frkl* does: expanding (and also modifying if wanted) configuration from as minimal as possible to as comprehensive as necessary.

Now, of course, in this example the reduction in size is not that big. And, one might argue, not having a fixed schema might not be a good idea in the first place. I can even see the point, but I do like being able to express myself as simple and minimal as possible. Obviously we are introducing more fragility by loosening up our schema. But we gain clarity, and ease of use. Whether this trade-off is justifiable or not depends on the situation I think. This library is for the situations where it is :-)

Also, just so you know, *frkl* has a few more tricks up its sleeve. For those, check out the yet to be written configuration at this yet to be created `link <http://go.somewhere.com>`_

*frkl* is written in Python, and GPL v3 licensed (for now).

* Documentation: https://frkl.readthedocs.io.


Features
--------

* transform configurations, focusing on clarity and the removal of redundancy
* plug-able architecture
* pre-made string/object processors/filters (regex, url abbreviation, jinja templates, etc.)
* auto-downloading, merging of configuration items
* mix and match of local and remote configuration items
