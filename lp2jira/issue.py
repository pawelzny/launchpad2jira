# -*- coding: utf-8 -*-
import json
import logging
import os

from tqdm import tqdm

from lp2jira.lp import lp
from lp2jira.config import config
from lp2jira.attachment import create_attachments
from lp2jira.user import create_user
from lp2jira.utils import bug_template, clean_id, translate_priority, translate_status


def export_issues():
    logging.info('===== Export: Issues =====')
    project = lp.projects[config['launchpad']['project']]

    bug_tasks = project.searchTasks(
        status=['New', 'Incomplete', 'Opinion', 'Invalid', 'Won\'t Fix', 'Expired',
                'Confirmed', 'Triaged', 'In Progress', 'Fix Committed', 'Fix Released',
                'Incomplete (with response)', 'Incomplete (without response)'],
        information_type=['Public', 'Public Security', 'Private Security',
                          'Private', 'Proprietary', 'Embargoed'])

    export_bug = bug_template()
    export_bug['projects'][0]['versions'] = get_releases(project)

    counter = 0
    for task in tqdm(bug_tasks[:20], desc='Export issues'):
        bug = task.bug

        for activity in bug.activity:
            create_user(clean_id(activity.person_link))

        filename = os.path.normpath('%s/%s_issue.json' % (config['local']['issues'], bug.id))
        if os.path.exists(filename):
            counter += 1
            logging.info('Issue %s already exists, skipping: %s' % (bug.id, filename))
            continue

        logging.info('Issue %s fetch' % bug.id)
        try:
            issue, sub_tasks, links = create_issue(task, bug)
        except Exception as e:
            logging.error('Issue %s export failed' % bug.id)
            logging.exception(e)
        else:
            counter += 1
            export_bug['projects'][0]['issues'] = [issue] + sub_tasks
            export_bug['links'] = links

            with open(filename, 'w') as f:
                json.dump(export_bug, f)

            logging.info('Issue %s export success' % bug.id)
    logging.info('Exported issues: %s/%s' % (counter, len(bug_tasks)))


def create_issue(task, bug):
    issue = {
        'externalId': str(bug.id),
        'status': translate_status(task.status),
        'reporter': bug.owner.display_name,
        'assignee': task.assignee.display_name,
        'summary': bug.title,
        'description': bug.description,
        'priority': translate_priority(task.importance),
        'labels': bug.tags,
        'issueType': 'Bug',
        'created': task.date_created.isoformat(),
        'updated': bug.date_last_updated.isoformat(),
        'comments': [],
        'history': [],  # TODO: activities
        'affectedVersions': [],
        'attachments': create_attachments(bug)
    }

    for comment in bug.messages:
        c = {'body': comment.content,
             'created': comment.date_created.isoformat(),
             'author': clean_id(comment.owner_link)}
        create_user(c['author'])
        issue['comments'].append(c)

    sub_tasks = []
    links = []
    for activity in bug.activity:
        if activity.whatchanged == 'nominated for series':
            version = activity.newvalue.split('/')[-1]
            issue['affectedVersions'].append(version)

        if activity.whatchanged == 'bug task added':
            version = activity.newvalue.split('/')[-1]
            sub_task = {
                'externalId': '%s/%s' % (bug.id, len(sub_tasks) + 1),
                'status': translate_status(task.status),
                'reporter': get_username(activity.person_link),
                'assignee': task.assignee.display_name,
                'summary': 'Nominated for series: %s' % version,
                'issueType': 'Sub-task',
                'created': activity.datechanged.isoformat()
            }
            sub_tasks.append(sub_task)

            links.append({
                'name': 'sub-task-link',
                'sourceId': sub_task['externalId'],
                'destinationId': issue['externalId']
            })

        if activity.whatchanged == 'tags':
            issue['labels'].extend(activity.newvalue.split())

        if activity.whatchanged == 'bug task deleted':
            version = activity.oldvalue.split('/')[-1]
            sub_tasks = [s for s in sub_tasks
                         if s['summary'] != 'Nominated for series: %s' % version]
    return issue, sub_tasks, links


def get_releases(project):
    releases = []
    for release in project.releases:
        r = {'name': release.version}
        if hasattr(release, 'date_released'):
            r['releaseDate'] = release.date_released.isoformat()
            r['released'] = True
        releases.append(r)
    return releases


def get_username(owner_link):
    owner_id = clean_id(owner_link)
    return lp.people[owner_id].display_name
