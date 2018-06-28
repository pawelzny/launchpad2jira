========================
Launchpad to JIRA export
========================

:Info: Export users and issues from Launchpad project to JIRA.
:Author: Paweł Zadrożny @pawelzny <pawel.zny@gmail.com>

This little command line script allow to export all Issues and Users
from launchpad to JSON file which is compatible with default JIRA's import plugin.


TODO
====

**Warning! Work in progress. Few things are still missing.**

* Export issue history (activities)
* Export blueprints
* Support for custom fields
* Export components


Installation
============

Prepare virtual environment first unless you don't care about PIP libs.

.. code-block:: console

    pip install -r requirements.txt

All required libraries will be installed in to your system or virtualenv.


Configuration
=============

Configuration required to edit config and mapping files.

Export.conf
-----------

Edit `export.conf` file.
The most important configuration you have to change are:

.. code-block:: ini

    [launchpad]
    # Project short name on Launchpad [required]
    project =

    [jira]
    # Project name on JIRA [required]
    project =

    # Project key on JIRA [required]
    key =

    # To which groups users will be assigned to [optional]
    groups =

    # URL to server where exported attachments are visible to JIRA instance
    attachments_url = http://localhost/attachments/


You don't need to change anything in other sections.

Issue status mapping
--------------------

Edit `mapping/lp2jira_issue.json` file.
This file provides mapping between issues statuses from Launchpad to JIRA.
All *keys* are statuses from Launchpad, and *values* are statuses from JIRA.

Values must be exact names of statuses from JIRA.
You can check on http://<my-jira.com>/secure/admin/ViewStatuses.jspa

Importance to priority mapping
------------------------------

Edit `mapping/lp2jira_priority.json` file.
This file provides mapping between Launchpad importance and JIRA priority
status. All *keys* are statuses from Launchpad, and *values* are statuses from JIRA.

Values must be exact names of priorities from JIRA.
You can check on http://<my-jira.com>/secure/admin/ViewPriorities.jspa

Run Export
==========

Execute `LaunchpadExport.py` file.

.. code-block::

    ./LaunchpadExport.py

Two directories will be created

* `.lplib_cache` - used by launchpad library
* `<launchpad:project>_export` - used to save exported files

Final JSON file will be in `<launchpad:project>_export/<launchpad:project>_export.json`.


History
=======

**2018-06-28 [dev]:**

* Export issues (bugs)
    * comments
    * attachments
    * status mapping
    * priority mapping
    * sub-tasks based on affected branches
* Export releases
* Export users
    * subscribed to project
    * commenter
    * assignee
    * reporter


LICENSE
=======

The MIT License (MIT)

Copyright (c) 2018 Paweł Zadrożny

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
