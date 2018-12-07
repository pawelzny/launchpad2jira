# -*- coding: utf-8 -*-
import logging
import os
import json
import requests
import dateutil.parser
import re

from tqdm import tqdm

from bs4 import BeautifulSoup

from lp2jira.attachment import create_attachments
from lp2jira.config import config, lp
from lp2jira.export import Export
from lp2jira.user import ExportUser, User
from lp2jira.utils import (bug_id, bug_template, clean_id, convert_custom_field_type,
                           get_custom_fields, get_owner,
                           get_user_data_from_activity_changed, json_dump,
                           translate_priority, translate_status, translate_blueprint_status)


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
            username = clean_id(self.owner)
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
        name = f'{issue_id.replace("/", "_")}.json'
        return os.path.normpath(os.path.join(config["local"]["issues"], name))

    @staticmethod
    def exists(issue_id):
        return os.path.exists(Issue.filename(issue_id))

    def _dump(self):
        issue = {
            'externalId': self.issue_id,
            'status': self.status,
            'reporter': clean_id(self.owner),
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
                       'sourceId': bug_id(d, task.bug_target_name),
                       'destinationId': bug_id(task)} for d in bug.duplicates]

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
                    'author': clean_id(activity.person_link),
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
                    'author': clean_id(activity.person_link),
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

                sub_task = SubTask(issue_id=f'{bug_id(task)}/{len(sub_tasks) + 1}',
                                   status=translate_status(bug_task.status),
                                   owner=clean_id(bug_task.owner_link),
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
                    'destinationId': bug_id(task)
                })

            elif (not '/' in bug_task.bug_target_name and
                  bug_task.bug_target_name != config['launchpad']['project']):

                links.append({
                    'name': 'Related',
                    'sourceId': bug_id(bug_task),
                    'destinationId': bug_id(task)
                })

        if task.milestone_link:
            fixed_versions.append(task.milestone.name)

        return cls(issue_id=bug_id(task), status=translate_status(task.status), owner=clean_id(bug.owner_link),
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
                username = clean_id(sub_task.owner)
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

            if super().run(task=task, bug=bug, releases=releases):
                counter += 1
            else:
                failed_issues.append(f'index: {index}, id: {bug_id(task)}')

        logging.info(f'Exported issues: {counter}/{len(bug_tasks)}')
        if failed_issues:
            fail_log = '\n'.join(failed_issues)
            logging.info(f'Failed issues:\n{fail_log}')

class UpdateBugs:
    def __init__(self):
        self.username = config['jira']['username']
        self.password = config['jira']['password']
        self.server = config['jira']['server']
        self.json_path = os.path.join(config['local']['export'], config['jira']['issues'])
        self.update_path = os.path.join(config['local']['export'], config['jira']['update'])

        with open(config['mapping']['custom_fields']) as f:
            mapping = json.load(f)
            self.id_cf_number = mapping['id']['fieldName'].split('_')[-1]

        with open(self.json_path, 'r') as f:
            self.lp_issues = json.load(f)['projects'][0]['issues']

    def run(self):
        updated_issues = bug_template()

        for index, lp_issue in enumerate(tqdm(self.lp_issues, desc="Update issues")):
            external_id = lp_issue['externalId']

            jira_search_result = self.find_lp_issue_in_jira(lp_issue, external_id)

            if not jira_search_result['issues']:
                updated_issues['projects'][0]['issues'].append(lp_issue)
                continue

            full_jira_issue = self.find_correct_issue(jira_search_result, external_id)
            jira_project = full_jira_issue['projects'][0]
            jira_issue = jira_project['issues'][0]


            self.add_new(updated_issues['projects'][0]['versions'], jira_project['versions'])
            self.add_new(updated_issues['users'], full_jira_issue['users'])

            if not self.should_update(lp_issue, jira_issue):
                continue

            for key, value in jira_issue.items():
                if key not in lp_issue:
                    continue

                if isinstance(value, list):
                    if key == 'comments':
                        jira_issue[key] = self.clear_comments(lp_issue[key],
                                                              jira_issue[key])
                    elif key == 'history':
                        jira_issue[key] = self.clear_history(lp_issue[key],
                                                             jira_issue[key])
                    else:
                        jira_issue[key] = lp_issue[key]
                else:
                    jira_issue[key] = lp_issue[key]

            updated_issues['projects'][0]['issues'].append(jira_issue)

        self.export_update(updated_issues)

    def verify_update(self):
        with open(config['mapping']['issue']) as f:
            status_mapping = json.load(f)

        msgs = []
        failed_update = 0
        failed_status = 0
        failed_unexpected = 0
        for index, lp_issue in enumerate(tqdm(self.lp_issues, desc="Verify")):
            external_id = lp_issue['externalId']
            try:
                jira_search_result = self.find_lp_issue_in_jira(lp_issue, external_id)
                if not jira_search_result['issues']:
                    msgs.append(f"Launchpad issue with externalID: {external_id} not found in Jira.")
                    failed_update += 1
                else:
                    full_jira_issue = self.find_correct_issue(jira_search_result, external_id)
                    lp_status = lp_issue['status']
                    try:
                        translated_lp_status = status_mapping[lp_status]
                    except KeyError:
                        if full_jira_issue['projects'][0]['issues'][0]['issueType'] == "Story":
                            project = lp.projects[config['launchpad']['project']]
                            spec = project.getSpecification(name=external_id)
                            translated_lp_status = translate_blueprint_status(spec)
                        else:
                            translated_lp_status = lp_issue['status']

                    jira_status = full_jira_issue['projects'][0]['issues'][0]['status']
                    if translated_lp_status != jira_status:
                        failed_status += 1
                        msgs.append(f"Launchpad issue with externalID: {external_id} has incorrect status.")
                        msgs.append(f"Original Launchpad status: {lp_status}, Jira status: {jira_status}.\n")
            except Exception as exc:
                msgs.append(f"Exception raised when verify issue with externalID {externalID}.")
                failed_unexpected += 0
                logging.error(f"Exception raised when verify issue with externalID {externalID}.")
                info = getattr(exc, 'doc', None)
                if info:
                    logging.error(f"Response being parsed by json: {info}")
                logging.exception(exc)

        if not (failed_update or failed_status or failed_unexpected):
            msgs.append("Verify completed successfully! All tickets have been imported. All statuses verified.")
        else:
            lp_issue_amount = len(self.lp_issues)
            msgs.append(f"Verified {lp_issue_amount - failed_update - failed_status - failed_unexpected} of {lp_issue_amount}.")
            if failed_update:
                msgs.append(f"{failed_update} tickets could not be found in Jira.")
            if failed_status:
                msgs.append(f"{failed_status} ticket statuses could not be verified.")
            if failed_unexpected:
                msgs.append(f"{failed_unexpected} exception raised when try to verify.")
        log = '\n'.join(msgs)
        print(log)
        logging.info(f"Verify log:\n{log}")

    def export_update(self, updated_issues):
        from lp2jira.utils import json_dump
        with open(self.update_path, 'w') as f:
            json_dump(updated_issues, f)

    def normalize_datetimes(self, lp_datetime, jira_datetime):
        lp_timestamp = int(dateutil.parser.parse(lp_datetime).timestamp())
        jira_timestamp = int(jira_datetime / 1e3)
        return lp_timestamp, jira_timestamp

    def should_update(self, lp_issue, jira_issue):
        if 'updated' not in lp_issue:
            return True

        lp_raw_date = lp_issue['updated']
        jira_raw_date = jira_issue['updated']
        lp_updated, jira_updated = self.normalize_datetimes(lp_raw_date,
                                                            jira_raw_date)
        return lp_updated > jira_updated

    def add_new(self, old, new):
        for i in new:
            if i not in old:
                old.append(i)

    def clear_comments(self, lp_comments, jira_comments):
        cleared_comments = []
        for comment in lp_comments:
            if not self.has_comment(jira_comments, comment):
                cleared_comments.append(comment)
        return cleared_comments

    def has_comment(self, jira_comments, lp_comment):
        for comment in jira_comments:
            lp_created, jira_created = self.normalize_datetimes(lp_comment['created'],
                                                                comment['created'])
            if not 'body' in comment:
                return True
            if comment['body'] == lp_comment['body'] and lp_created == jira_created:
                return True
        return False
    
    def clear_history(self, lp_history, jira_history):
        cleared_history = []
        for record in lp_history:
            if not self.has_record(jira_history, record):
                cleared_history.append(record)
        return cleared_history

    def has_record(self, jira_history, lp_record):
        for record in jira_history:
            lp_created, jira_created = self.normalize_datetimes(lp_record['created'],
                                                                record['created'])
            if record['author'] == lp_record['author'] and lp_created == jira_created:
                return True
        return False

    def find_lp_issue_in_jira(self, lp_issue, external_id):
        is_blueprint = lp_issue["issueType"] == "Story"
        if is_blueprint or "/" not in external_id:
            cf_id = external_id
        else:
            cf_id = external_id.split('/')[1]
        return self.search_jira_for_issue(cf_id, is_blueprint)

    def find_correct_issue(self, jira_search_result, externalId):
        for issue in jira_search_result['issues']:
            full_jira_issue = self.get_full_jira_issue(issue['key'])
            for custom_field in full_jira_issue['projects'][0]['issues'][0]['customFieldValues']:
                    if custom_field['value'] == externalId:
                        return full_jira_issue

    def search_jira_for_issue(self, external_id, is_blueprint):
        if is_blueprint:
            url = f'{self.server}/rest/api/2/search?jql=text~{external_id}'
        else:
            url = f'{self.server}/rest/api/2/search?jql=cf[{self.id_cf_number}]~{external_id}'
        return requests.get(url, auth=(self.username, self.password)).json()
    
    def get_full_jira_issue(self, issue_key):
        url = f'{self.server}/si/com.atlassian.jira.plugins.jira-importers-plugin:issue-json/{issue_key}/{issue_key}.json'
        return requests.get(url, auth=(self.username, self.password)).json()