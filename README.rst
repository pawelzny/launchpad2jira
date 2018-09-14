========================
Launchpad to JIRA export
========================

:Info: Export users and issues from Launchpad project to JIRA.
:Author: Paweł Zadrożny @pawelzny <pawel.zny@gmail.com>

This little command line script allow to export all Issues and Users
from launchpad to JSON file which is compatible with default JIRA's import plugin.


TODO
====

* Export issue history (activities)


Installation
============

** Require: Python 3.6 **

Prepare virtual environment first unless you don't care about PIP libs.

.. code-block:: console

    python3.6 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

All required libraries will be installed in to your system or virtualenv.


Configuration
=============

Configuration required to edit config and mapping files.

Export.cfg
----------

Edit `export.cfg` file.
The most important configuration you have to change are:

.. code-block:: ini

    [DEFAULT]
    # Export custom fields defined in mapping file
    export_custom_fields = true

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

    [mapping]
    # Blueprint default status
    blueprint_default = New

    # Launchpad Bug task to JIRA issue_type conversion.
    # Bug is a main task you can find in Launchpad.
    bug_type = Bug

    # Launchpad Bug sub-task to JIRA issue_type conversion.
    # Every bug can have multiple sub-tasks related to affected versions
    sub_task_type = Sub-task

    # Launchpad Blueprint to JIRA issue_type conversion.
    # Blueprints are proposals for new features or big changes.
    blueprint_type = Story


You don't need to change anything in other sections.

Issue status mapping
--------------------

Edit `mapping/lp2jira_issue.json` file.
This file provides mapping between issues statuses from Launchpad to JIRA.
All *keys* are statuses from Launchpad, and *values* are statuses from JIRA.

Values must be exact names of statuses from JIRA.
You can check on http://<my-jira.com>/secure/admin/ViewStatuses.jspa

Issue status mapping for blueprints
-----------------------------------

Edit `mapping/lp2jira_blueprint.json` file.
This file provides mapping between issues statuses from Launchpad to JIRA.
All conditions are check one by one and first match wins.

Status value must be exact name of status defined in JIRA.
You can check on http://<my-jira.com>/secure/admin/ViewStatuses.jspa

Importance to priority mapping
------------------------------

Edit `mapping/lp2jira_priority.json` file.
This file provides mapping between Launchpad importance and JIRA priority
status. All *keys* are statuses from Launchpad, and *values* are statuses from JIRA.

Values must be exact names of priorities from JIRA.
You can check on http://<my-jira.com>/secure/admin/ViewPriorities.jspa

Custom fields mapping
---------------------

Edit `mapping/lp2jira_custom_fields.json` file.
This file provides mapping between Launchpad any field and JIRA custom field.
All *keys* are keys from Launchpad, and *values* are mapping to JIRA custom field.

Any Launchpad key can be mapped to JIRA custom field. Script will lookup
if defined key exists on Launchpad side and will apply mapping.

Run Export
==========

Execute `LaunchpadExport.py` file.

.. code-block:: console

    ./LaunchpadExport.py

Optional arguments: `--only-bugs`, `--only-blueprints` to export only this part.

Two directories will be created

* `.lplib_cache` - used by launchpad library
* `<launchpad:project>_export` - used to save exported files

Final JSON file will be in `<launchpad:project>_export/<launchpad:project>_export.json`.


History
=======

**2018-09-14**

* Changed
    ** Export subtasks related only to acctual project

* Fixed
    ** Get fixedVersions from subtasks

**2018-09-05**

* Fixed
    * Exporting duplicated issues

**2018-09-03**

* Fixed
    * Spaces in attachment's name, username in attacher
    * Leaving links to deleted subtasks

**2018-08-31:**

* Changed
    * Skip existing files before querying API
    * Remove duplicated comments and SubTasks

* Fixed
    * Include affected versions in SubTasks
    * Use username in Reporter, Assignee fields

**2018-08-30:**

* Fixed
    * White characters in attachment file names

**2018-08-29:**

* Added
    * Custom fields for SubTasks
    * Logging failed exports in summary
    * Status for Blueprints from multiple custom fields
* Fixed
    * Issue file name too long

**2018-08-28 [dev]:**

* Added
    * Custom field type converter
    * Link duplicated issues
* Fixed
    * Add versions from issue milestones
    * Export users which are involve in Bugs
    * Attachment filename reference
    * Tags export

**2018-08-23 [dev]:**

* Changed:
    * Exit gracefully on KeyboardInterrupt exception
* Added
    * Launchpad milestones to JIRA fixedVersions mapping
* Fixed
    * Missing versions list

**2018-07-15 [dev]:**

* Added
    * support for custom fields
    * configurable issues type

**2018-06-28 [dev]:**

* Added
    * **Export issues (bugs)**
        * comments
        * attachments
        * status mapping
        * priority mapping
        * sub-tasks based on affected branches
    * **Export blueprints**
        * status mapping
        * priority mapping
        * reporter and assignee
        * description, whiteboard, work items
    * **Export users**
        * subscribed to project
        * commenter
        * assignee
        * reporter
    * **Export releases**


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
