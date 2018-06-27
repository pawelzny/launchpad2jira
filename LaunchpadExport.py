#!/usr/bin/env python
# coding: utf-8
import json
import logging
import os

import configparser
from launchpadlib.launchpad import Launchpad
from tqdm import tqdm


def get_username(owner_link):
    owner_id = clean_id(owner_link)
    return lp.people[owner_id].display_name


def clean_id(item_id):
    tail = item_id.split('/')[-1]
    return tail.lstrip('~')


def translate_status(status):
    with open(config['jira']['mapping'], 'r') as f:
        mapping = json.load(f)
    return mapping[status.title()]


def create_attachment(bug):
    for attachment in bug.attachments:
        f_in = attachment.data.open()
        filename = os.path.normpath('%s/%s_%s' % (config['local']['attachments'],
                                                  bug.id, f_in.filename))

        if os.path.exists(filename):
            logging.info('Attachment %s_%s already exists, '
                         'skipping: %s' % (bug.id, f_in.filename, filename))
        else:
            with open(filename, 'wb') as f_out:
                while True:
                    buff = f_in.read(1024)
                    if buff:
                        f_out.write(buff)
                    else:
                        break
            logging.info('Attachment %s_%s export success' % (bug.id, f_in.filename))

        return {
            'name': f_in.filename,
            'attacher': attachment.message.owner.display_name,
            'created': attachment.message.date_created.isoformat(),
            'uri': '%s/%s' % (config['jira']['attachments_url'].rstrip('/'), f_in.filename)
        }


def create_issue(task, bug):
    issue = {
        'externalId': str(bug.id),
        'status': translate_status(task.status),
        'reporter': bug.owner.display_name,
        'assignee': task.assignee.display_name,
        'summary': bug.title,
        'description': bug.description,
        'priority': task.importance,
        'labels': bug.tags,
        'issueType': 'Bug',
        'created': task.date_created.isoformat(),
        'updated': bug.date_last_updated.isoformat(),
        'comments': [{'body': c.content,
                      'created': c.date_created.isoformat(),
                      'author': get_username(c.owner_link)}
                     for c in bug.messages],
        'history': [],  # TODO: activities
        'affectedVersions': [],
        'attachments': create_attachment(bug)
    }
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


def export_issues():
    logging.info('===== Export: Issues =====')
    project = lp.projects[config['launchpad']['project']]

    bug_tasks = project.searchTasks(
        status=['New', 'Incomplete', 'Opinion', 'Invalid', 'Won\'t Fix', 'Expired',
                'Confirmed', 'Triaged', 'In Progress', 'Fix Committed', 'Fix Released',
                'Incomplete (with response)', 'Incomplete (without response)'],
        information_type=['Public', 'Public Security', 'Private Security',
                          'Private', 'Proprietary', 'Embargoed'])

    counter = 0
    for task in tqdm(bug_tasks[:20], desc='Export issues'):  # TODO: remove slice
        bug = task.bug

        for activity in bug.activity:
            create_user(clean_id(activity.person_link), [])

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

            with open(filename, 'wb') as f:
                json.dump(export_bug, f)

            logging.info('Issue %s export success' % bug.id)
    logging.info('Exported issues: %s/%s' % (counter, len(bug_tasks)))


def create_user(username, groups):
    filename = os.path.normpath('%s/%s_user.json' % (config['local']['users'], username))
    if os.path.exists(filename):
        logging.info('User %s already exists, skipping: %s' % (username, filename))
        return True

    try:
        lp_user = lp.people[username]
    except Exception as e:
        logging.error('User %s export failed' % username)
        logging.exception(e)
        return False
    else:
        email = None
        if not lp_user.hide_email_addresses and lp_user.preferred_email_address:
            email = lp_user.preferred_email_address.email

        user = {
            'name': username,
            'fullname': lp_user.display_name,
            'active': True,
        }

        if groups:
            user['groups'] = groups
        if email:
            user['email'] = email

        with open(filename, 'wb') as f:
            json.dump(user, f)

        logging.info('User %s export success' % username)
        return True


def export_users():
    logging.info('===== Export: Users =====')

    groups = []
    if config['jira']['groups']:
        groups = [g.strip() for g in config['jira']['groups'].split(',')]

    project = lp.projects[config['launchpad']['project']]
    subscriptions = project.getSubscriptions()

    counter = 0
    for sub in tqdm(subscriptions, desc='Export users'):
        username = clean_id(sub.subscriber_link)
        if create_user(username, groups):
            counter += 1
    logging.info('Exported users: %s/%s' % (counter, len(subscriptions)))


def compile_export_file():
    logging.info('===== Compile export file =====')

    export_bug['projects'][0]['issues'] = []
    for filename in tqdm(os.listdir(config['local']['issues']), desc='Compile issues'):
        with open(os.path.join(config['local']['issues'], filename), 'r') as f:
            issue = json.load(f)
        export_bug['projects'][0]['issues'].extend(issue['projects'][0]['issues'])
        export_bug['links'].extend(issue['links'])

    for filename in tqdm(os.listdir(config['local']['users']), desc='Compile users'):
        with open(os.path.join(config['local']['users'], filename), 'r') as f:
            user = json.load(f)
        export_bug['users'].append(user)

    logging.info('Compiled issues: %s', len(export_bug['projects'][0]['issues']))
    logging.info('Compiled links: %s', len(export_bug['links']))
    logging.info('Compiled users: %s', len(export_bug['users']))

    filename = os.path.join(config['local']['export'], config['jira']['filename'])
    with open(filename, 'wb') as f:
        json.dump(export_bug, f)

    logging.info('Exported data saved in: %s' % filename)


def main():
    logging.info('===== Export start =====')
    export_users()
    export_issues()
    compile_export_file()
    logging.info('===== Export complete =====')


if __name__ == '__main__':
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    config.read('export.conf')

    logging.basicConfig(filename=config['logging']['filename'],
                        format=config['logging']['format'],
                        level=config['logging']['level'])

    lp = Launchpad.login_with('LP2JIRA', config['launchpad']['service'],
                              launchpadlib_dir=config['launchpad']['cache_dir'])

    export_bug = {
        'users': [],
        'links': [],
        'projects': [
            {
                'name': config['jira']['project'],
                'key': config['jira']['key'],
                'type': 'software',
                'issues': [],
            },
        ],
    }

    for directory in config['local'].values():
        if not os.path.exists(directory):
            os.mkdir(directory)

    main()
