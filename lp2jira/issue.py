# -*- coding: utf-8 -*-
import logging
import os

from tqdm import tqdm

from lp2jira.attachment import create_attachments
from lp2jira.config import config, lp
from lp2jira.export import Export
from lp2jira.user import ExportUser, User
from lp2jira.utils import (bug_template, clean_id, convert_custom_field_type,
                           get_custom_fields, get_owner,
                           get_user_data_from_activity_changed, json_dump,
                           translate_priority, translate_status)


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
            username = clean_id(self.owner.name)
            if not User.exists(username):
                self.export_user(username)
        except Exception as exc:
            logging.exception(exc)
        try:
            if self.assignee:
                username = clean_id(self.assignee.name)
                if not User.exists(username):
                    self.export_user(username)
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

    @staticmethod
    def filename(issue_id):
        return os.path.normpath(os.path.join(config["local"]["issues"], f'{issue_id}.json'))

    @staticmethod
    def exists(issue_id):
        return os.path.exists(Issue.filename(issue_id))

    def _dump(self):
        issue = {
            'externalId': self.issue_id,
            'status': self.status,
            'reporter': self.owner.name,
            'summary': self.title,
            'description': self.desc,
            'priority': self.priority,
            'issueType': self.issue_type,
            'created': self.created,
            'labels': list(self.tags),
        }
        if self.assignee:
            issue['assignee'] = self.assignee.name
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
        comments = cls._collect_comments(bug.messages)

        duplicates = [{'name': 'Duplicate',
                       'sourceId': str(d.id),
                       'destinationId': str(bug.id)} for d in bug.duplicates]

        custom_fields = Issue.create_custom_fields(task)
        custom_fields.extend(Issue.create_custom_fields(bug))

        sub_tasks = []
        affected_versions = []
        tags = bug.tags
        subtask_history = {}
        history = []
        for activity in bug.activity:
            if activity.whatchanged == 'tags':
                history.append({
                    'author': get_owner(activity.person_link).name,
                    'created': activity.datechanged.isoformat(),
                    'items': [{
                        'fieldType': 'jira',
                        'field': 'labels',
                        'from': None,
                        'fromString': activity.oldvalue,
                        'to': None,
                        'toString': activity.newvalue
                    }]
                })

            if 'assignee' in activity.whatchanged:
                subtask_target = activity.whatchanged.split(':')[0]

                if not subtask_target in subtask_history:
                    subtask_history[subtask_target] = []

                old_display, old_name = get_user_data_from_activity_changed(activity.oldvalue)
                new_display, new_name = get_user_data_from_activity_changed(activity.newvalue)

                subtask_history[subtask_target].append({
                    'author': get_owner(activity.person_link).name,
                    'created': activity.datechanged.isoformat(),
                    'items': [{
                        'fieldType': 'jira',
                        'field': 'assignee',
                        'from': old_name,
                        'fromString': old_display,
                        'to': new_name,
                        'toString': new_display
                    }]
                })

        links = []
        fixed_versions = []
        for bug_task in bug.bug_tasks:
            if bug_task.bug_target_name.startswith(f"{config['launchpad']['project']}/"):
                version = bug_task.bug_target_name.split('/')[-1]
                affected_versions.append(version)

                sub_task = SubTask(issue_id=f'{bug.id}/{len(sub_tasks) + 1}',
                                   status=translate_status(bug_task.status),
                                   owner=bug_task.owner,
                                   assignee=bug_task.assignee,
                                   title=f'[{bug_task.bug_target_name}] {bug_task.title}',
                                   desc=bug.description, priority=bug_task.importance,
                                   created=bug_task.date_created.isoformat(), tags=tags,
                                   custom_fields=custom_fields, affected_versions=[version],
                                   history=subtask_history.get(bug_task.bug_target_name, []))
                sub_tasks.append(sub_task)

                if bug_task.milestone_link:
                    fixed_versions.append(bug_task.milestone.name)

                links.append({
                    'name': 'sub-task-link',
                    'sourceId': sub_task.issue_id,
                    'destinationId': str(bug.id),
                })

        if task.milestone_link:
            fixed_versions.append(task.milestone.name)

        return cls(issue_id=bug.id, status=translate_status(task.status), owner=bug.owner,
                   assignee=task.assignee, title=bug.title, desc=bug.description,
                   priority=task.importance, tags=tags, created=task.date_created.isoformat(),
                   updated=bug.date_last_updated.isoformat(), comments=comments,
                   history=history + subtask_history.get(config['launchpad']['project'], []),
                   affected_versions=affected_versions, attachments=create_attachments(bug),
                   sub_tasks=sub_tasks, links=links, releases=releases, duplicates=duplicates,
                   custom_fields=custom_fields, fixed_versions=fixed_versions)

    def export(self):
        self._export_related_users()

        filename = self.filename(self.issue_id)
        if self.exists(self.issue_id):
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
                username = clean_id(comment['author'])
                if not User.exists(username):
                    self.export_user(username)
            except Exception as exc:
                logging.exception(exc)

        for sub_task in self.sub_tasks:
            try:
                username = clean_id(sub_task.owner.name)
                if not User.exists(username):
                    self.export_user(username)
            except Exception as exc:
                logging.exception(exc)

    @classmethod
    def _collect_comments(cls, messages):
        comments = []
        shared_etag = ""
        for comment in messages:
            new_etag = comment.http_etag.split('-')[1]
            if shared_etag != new_etag:
                comments.append({'body': comment.content,
                                 'created': comment.date_created.isoformat(),
                                 'author': clean_id(comment.owner_link)})
                shared_etag = new_etag
        return comments


class SubTask(Issue):
    issue_type = config['mapping']['sub_task_type']

    def __init__(self, issue_id, status, owner, assignee, title, desc, tags,
                 priority, created, custom_fields, affected_versions, history):
        super().__init__(issue_id, status, owner, assignee, title, desc, tags,
                         priority, created, custom_fields, affected_versions)
        self.history = history

    def _dump(self):
        issue = super()._dump()
        issue.update({
            'affectedVersions': self.affected_versions,
            'history': self.history
        })
        return issue


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
                              'Private', 'Proprietary', 'Embargoed'],
            omit_duplicates=False)
        releases = get_releases(project)

        failed_issues = []
        counter = 0
        for index, task in enumerate(tqdm(bug_tasks, desc='Export issues')):
            bug = task.bug
            if Issue.exists(bug.id):
                counter += 1
                continue

            if super().run(task=task, bug=bug, releases=releases):
                counter += 1
            else:
                failed_issues.append(f'index: {index}, id: {bug.id}')

        logging.info(f'Exported issues: {counter}/{len(bug_tasks)}')
        if failed_issues:
            fail_log = '\n'.join(failed_issues)
            logging.info(f'Failed issues:\n{fail_log}')
