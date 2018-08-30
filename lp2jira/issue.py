# -*- coding: utf-8 -*-
import logging
import os

from tqdm import tqdm

from lp2jira.attachment import create_attachments
from lp2jira.config import config, lp
from lp2jira.export import Export
from lp2jira.user import ExportUser
from lp2jira.utils import (bug_template, clean_id, convert_custom_field_type, get_custom_fields,
                           get_owner, json_dump, translate_priority, translate_status)


def get_releases(project):
    releases = []
    for release in project.releases:
        r = {'name': release.version}
        if hasattr(release, 'date_released'):
            r['releaseDate'] = release.date_released.isoformat()
            r['released'] = True
        releases.append(r)
    return releases


def convert_versions(versions):
    return [{'name': str(v)} for v in versions]


class Issue:
    issue_type = 'Task'

    def __init__(self, issue_id, status, owner, assignee, title, desc, tags,
                 priority, created, custom_fields, affected_versions):
        self.issue_id = str(issue_id)
        self.status = status
        self.owner = owner
        self.assignee = assignee or None
        self.title = title
        self.desc = desc
        self.tags = tags
        self.priority = translate_priority(priority)
        self.created = created
        self.custom_fields = custom_fields
        self.affected_versions = affected_versions
        self.export_user = ExportUser()

    def _export_related_users(self):
        try:
            self.export_user(username=clean_id(self.owner.name))
        except Exception as exc:
            logging.exception(exc)
        try:
            if self.assignee:
                self.export_user(username=clean_id(self.assignee.name))
        except Exception as exc:
            logging.exception(exc)

    @staticmethod
    def create_custom_fields(lp_entity):
        customs = []
        if config['DEFAULT'].getboolean('export_custom_fields'):
            for key, val in get_custom_fields().items():
                if hasattr(lp_entity, key):
                    lp_val = getattr(lp_entity, key)
                    val['value'] = convert_custom_field_type(val['fieldType'], lp_val)
                    customs.append(val)
        return customs

    def _dump(self):
        issue = {
            'externalId': self.issue_id,
            'status': self.status,
            'reporter': self.owner.display_name,
            'summary': self.title,
            'description': self.desc,
            'priority': self.priority,
            'issueType': self.issue_type,
            'created': self.created,
            'labels': list(self.tags),
        }
        if self.assignee:
            issue['assignee'] = self.assignee.display_name
        if self.custom_fields:
            issue['customFieldValues'] = self.custom_fields
        return issue


class Bug(Issue):
    issue_type = config['mapping']['bug_type']

    def __init__(self, issue_id, status, owner, assignee, title, desc, priority, tags,
                 created, updated, comments, history, affected_versions, attachments, sub_tasks,
                 links, releases, custom_fields, fixed_versions, duplicates):
        super().__init__(issue_id, status, owner, assignee, title, desc, tags,
                         priority, created, custom_fields, affected_versions)

        self.updated = updated
        self.comments = comments
        self.history = history  # TODO: activities
        self.fixed_versions = fixed_versions
        self.attachments = attachments
        self.sub_tasks = sub_tasks
        self.links = links
        self.releases = releases
        self.duplicates = duplicates

    @classmethod
    def create(cls, task, bug, releases):
        comments = [{'body': c.content,
                     'created': c.date_created.isoformat(),
                     'author': clean_id(c.owner_link)} for c in bug.messages]

        duplicates = [{'name': 'Duplicate',
                       'sourceId': str(d.id),
                       'destinationId': str(d.id)} for d in task.bug.duplicates]

        custom_fields = Issue.create_custom_fields(task)
        custom_fields.extend(Issue.create_custom_fields(bug))

        sub_tasks = []
        affected_versions = []
        tags = bug.tags
        links = []
        for activity in bug.activity:
            if activity.whatchanged == 'nominated for series':
                version = activity.newvalue.split('/')[-1]
                affected_versions.append(version)

            if activity.whatchanged == 'bug task added':
                version = activity.newvalue.split('/')[-1]

                sub_task = SubTask(issue_id=f'{bug.id}/{len(sub_tasks) + 1}',
                                   status=translate_status(task.status),
                                   owner=get_owner(activity.person_link),
                                   assignee=task.assignee,
                                   title=f'[{version}] {bug.title}',
                                   desc=bug.description, priority=task.importance,
                                   created=activity.datechanged.isoformat(), tags=tags,
                                   custom_fields=custom_fields, affected_versions=[version])
                sub_tasks.append(sub_task)
                links.append({
                    'name': 'sub-task-link',
                    'sourceId': sub_task.issue_id,
                    'destinationId': str(bug.id),
                })

            if activity.whatchanged == 'tags':
                tags.extend(activity.newvalue.split())

            if activity.whatchanged == 'bug task deleted':
                version = activity.oldvalue.split('/')[-1]
                sub_tasks = [s for s in sub_tasks if s.title != f'[{version}] {bug.title}']

        fixed_versions = []
        if task.milestone_link:
            fixed_versions.append(task.milestone.name)

        return cls(issue_id=bug.id, status=translate_status(task.status), owner=bug.owner,
                   assignee=task.assignee, title=bug.title, desc=bug.description,
                   priority=task.importance, tags=tags, created=task.date_created.isoformat(),
                   updated=bug.date_last_updated.isoformat(), comments=comments, history=[],
                   affected_versions=affected_versions, attachments=create_attachments(bug),
                   sub_tasks=sub_tasks, links=links, releases=releases, duplicates=duplicates,
                   custom_fields=custom_fields, fixed_versions=fixed_versions)

    def export(self):
        self._export_related_users()

        filename = os.path.normpath(os.path.join(config["local"]["issues"],
                                                 f'{self.issue_id}.json'))
        if os.path.exists(filename):
            logging.debug(f'Bug {self.issue_id} already exists, skipping: "{filename}"')
            return True

        versions = set(self.fixed_versions + self.affected_versions)
        all_versions = self.releases + convert_versions(versions)

        export_bug = bug_template()
        export_bug['projects'][0]['versions'] = all_versions
        export_bug['projects'][0]['issues'] = [self._dump()] + [s._dump() for s in self.sub_tasks]
        export_bug['links'] = self.links + self.duplicates

        with open(filename, 'w') as f:
            json_dump(export_bug, f)

        logging.debug(f'Bug {self.issue_id} export success')
        return True

    def _dump(self):
        issue = super()._dump()
        issue.update({'updated': self.updated,
                      'comments': self.comments,
                      'history': self.history,
                      'affectedVersions': self.affected_versions,
                      'fixedVersions': self.fixed_versions,
                      'attachments': self.attachments})
        return issue

    def _export_related_users(self):
        super()._export_related_users()
        for comment in self.comments:
            try:
                self.export_user(username=clean_id(comment['author']))
            except Exception as exc:
                logging.exception(exc)

        for sub_task in self.sub_tasks:
            try:
                self.export_user(username=clean_id(sub_task.owner.name))
            except Exception as exc:
                logging.exception(exc)


class SubTask(Issue):
    issue_type = config['mapping']['sub_task_type']


class ExportBug(Export):
    def __init__(self):
        super().__init__(entity=Bug)


class ExportBugs(ExportBug):
    def run(self):
        logging.info('===== Export: Issues =====')
        project = lp.projects[config['launchpad']['project']]

        bug_tasks = project.searchTasks(
            status=['New', 'Incomplete', 'Opinion', 'Invalid', 'Won\'t Fix', 'Expired',
                    'Confirmed', 'Triaged', 'In Progress', 'Fix Committed', 'Fix Released',
                    'Incomplete (with response)', 'Incomplete (without response)'],
            information_type=['Public', 'Public Security', 'Private Security',
                              'Private', 'Proprietary', 'Embargoed'])
        releases = get_releases(project)

        failed_issues = []
        counter = 0
        for index, task in enumerate(tqdm(bug_tasks, desc='Export issues')):
            bug = task.bug
            if super().run(task=task, bug=bug, releases=releases):
                counter += 1
            else:
                failed_issues.append(f'index: {index}, id: {bug.id}')

        logging.info(f'Exported issues: {counter}/{len(bug_tasks)}')
        if failed_issues:
            fail_log = '\n'.join(failed_issues)
            logging.info(f'Failed issues:\n{fail_log}')
