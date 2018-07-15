# -*- coding: utf-8 -*-
import json
import logging
import os

from tqdm import tqdm

from lp2jira.attachment import create_attachments
from lp2jira.config import config
from lp2jira.export import Export
from lp2jira.user import ExportUser
from lp2jira.lp import lp
from lp2jira.utils import bug_template, clean_id, translate_priority, translate_status


def get_releases(project):
    releases = []
    for release in project.releases:
        r = {'name': release.version}
        if hasattr(release, 'date_released'):
            r['releaseDate'] = release.date_released.isoformat()
            r['released'] = True
        releases.append(r)
    return releases


class Issue:
    def __init__(self, issue_id, status, owner, assignee, title, desc,
                 priority, issue_type, created):
        self.issue_id = str(issue_id)
        self.status = translate_status(status)
        self.owner = owner
        self.assignee = assignee.display_name if assignee else None
        self.title = title
        self.desc = desc
        self.priority = translate_priority(priority)
        self.issue_type = issue_type
        self.created = created.isoformat()
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

    def _dump(self):
        issue = {
            'externalId': self.issue_id,
            'status': self.status,
            'reporter': self.owner.display_name,
            'summary': self.title,
            'description': self.desc,
            'priority': self.priority,
            'issueType': self.issue_type,
            'created': self.created
        }
        if self.assignee:
            issue['assignee'] = self.assignee
        return issue


class Bug(Issue):
    def __init__(self, issue_id, status, owner, assignee, title, desc,
                 priority, tags, issue_type, created, updated, comments,
                 history, affected_versions, attachments, sub_tasks, links, releases):
        super().__init__(issue_id, status, owner, assignee, title, desc,
                         priority, issue_type, created)

        self.tags = tags
        self.updated = updated.isoformat()
        self.comments = comments
        self.history = history  # TODO: activities
        self.affected_versions = affected_versions
        self.attachments = attachments
        self.sub_tasks = sub_tasks
        self.links = links
        self.releases = releases

    @classmethod
    def create(cls, task, bug, releases):
        comments = [{'body': c.content,
                     'created': c.date_created.isoformat(),
                     'author': clean_id(c.owner_link)} for c in bug.messages]

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
                                   status=task.status, owner=clean_id(activity.person_link),
                                   assignee=task.assignee,
                                   title=f'Nominated for series: {version}',
                                   desc='', priority=task.importance, issue_type='Sub-task',
                                   created=activity.datechanged.isoformat())
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
                sub_tasks = [s for s in sub_tasks
                             if s.title != f'Nominated for series: {version}']

        return cls(issue_id=bug.id, status=task.status, owner=bug.owner, assignee=task.assignee,
                   title=bug.title, desc=bug.description, priority=task.importance,
                   tags=tags, issue_type='Bug', created=task.date_created.isoformat(),
                   updated=task.date_updated.isoformat(), comments=comments, history=[],
                   affected_versions=affected_versions, attachments=create_attachments(bug),
                   sub_tasks=sub_tasks, links=links, releases=releases)

    def export(self):
        filename = os.path.normpath(f'{config["local"]["issues"]}/{self.issue_id}_issue.json')
        if os.path.exists(filename):
            logging.info(f'Issue {self.issue_id} already exists, skipping: {filename}')
            return True

        logging.debug(f'Issue {self.issue_id} fetching')
        export_bug = bug_template()
        export_bug['projects'][0]['versions'] = self.releases
        export_bug['projects'][0]['issues'] = [self._dump()] + [s._dump() for s in self.sub_tasks]
        export_bug['links'] = self.links

        with open(filename, 'w') as f:
            json.dump(export_bug, f)

        logging.debug(f'Issue {self.issue_id} export success')
        return True

    def _dump(self):
        issue = super()._dump()
        issue.update({'labels': self.tags,
                      'updated': self.updated,
                      'comments': self.comments,
                      'history': self.history,
                      'affectedVersions': self.affected_versions,
                      'attachments': self.attachments})
        return issue

    def _export_related_users(self):
        super()._export_related_users()
        for comment in self.comments:
            self.export_user(username=comment['author'])

        for sub_task in self.sub_tasks:
            self.export_user(username=sub_task.owner)


class SubTask(Issue):
    pass


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

        counter = 0
        for task in tqdm(bug_tasks[:20], desc='Export issues'):
            if super().run(task=task, bug=task.bug, releases=get_releases(project)):
                counter += 1

        logging.info(f'Exported issues: {counter}/{len(bug_tasks)}')
