========================
Launchpad to JIRA export
========================

This little command line script allow to export all Issues and Users
from launchpad to JSON file which is compatible with default JIRA's import plugin.


Installation
============

Prepare virtual environment first unless you don't care about PIP libs.

.. code-block:: console

    pip install -r requirements.txt

All required libraries will be installed in to your system or virtualenv.


Configuration
=============

1. Edit `export.conf` file in sections: **launchpad** and **jira**.

The most important configuration you have to change are:

.. code-block::

    launchpad:project - name of existing project on launchpad

    jira:project      - name of project on jira
    jira:key          - project's key on jira
    jira:groups       - groups for exported users


You don't need to change anything in other sections.

2. Edit `lp2_jira_issue_map.json` file.

This file provides mapping between issues statuses from Launchpad to JIRA.
All *keys* are statuses from Launchpad, and *values* are statuses from JIRA.

Values must match exactly statuses from JIRA workflow.


Run Export
==========

Execute `LaunchpadExport.py` file.

.. code-block::

    ./LaunchpadExport.py

Two directories will be created

* .lplib_cache - used by launchpad library
* <launchpad:project>_export - used to save exported files

Final JSON file will be in `<launchpad:project>_export/<launchpad:project>_export.json`.


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
