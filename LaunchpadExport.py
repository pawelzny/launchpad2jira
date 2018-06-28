#!/usr/bin/env python
# coding: utf-8
import json
import logging
import os
import re

import configparser
import requests
from bs4 import BeautifulSoup
from launchpadlib.launchpad import Launchpad
from tqdm import tqdm


def get_username(owner_link):
    owner_id = clean_id(owner_link)
    return lp.people[owner_id].display_name


def clean_id(item_id):
    tail = item_id.split('/')[-1]
    return tail.lstrip('~')


def translate_status(status):
    with open(config['mapping']['issue'], 'r') as f:
        mapping = json.load(f)
    return mapping[status.title()]


def translate_priority(priority):
    with open(config['mapping']['priority'], 'r') as f:
        mapping = json.load(f)
    return mapping[priority.title()]


def create_attachments(bug):
    attachments = []
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
            attachments.append({
                'name': f_in.filename,
                'attacher': attachment.message.owner.display_name,
                'created': attachment.message.date_created.isoformat(),
                'uri': '%s/%s' % (config['jira']['attachments_url'].rstrip('/'), f_in.filename)
            })
    return attachments


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


def export_issues():
    logging.info('===== Export: Issues =====')
    project = lp.projects[config['launchpad']['project']]

    bug_tasks = project.searchTasks(
        status=['New', 'Incomplete', 'Opinion', 'Invalid', 'Won\'t Fix', 'Expired',
                'Confirmed', 'Triaged', 'In Progress', 'Fix Committed', 'Fix Released',
                'Incomplete (with response)', 'Incomplete (without response)'],
        information_type=['Public', 'Public Security', 'Private Security',
                          'Private', 'Proprietary', 'Embargoed'])

    export_bug['projects'][0]['versions'] = get_releases(project)

    counter = 0
    for task in tqdm(bug_tasks, desc='Export issues'):
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

            with open(filename, 'wb') as f:
                json.dump(export_bug, f)

            logging.info('Issue %s export success' % bug.id)
    logging.info('Exported issues: %s/%s' % (counter, len(bug_tasks)))


def create_user(username):
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

        if user_groups:
            user['groups'] = user_groups
        if email:
            user['email'] = email

        with open(filename, 'wb') as f:
            json.dump(user, f)

        logging.info('User %s export success' % username)
        return True


def export_users():
    logging.info('===== Export: Users =====')

    project = lp.projects[config['launchpad']['project']]
    subscriptions = project.getSubscriptions()

    counter = 0
    for sub in tqdm(subscriptions, desc='Export users'):
        username = clean_id(sub.subscriber_link)
        if create_user(username):
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


def export_blueprints():
    logging.info('===== Export: Blueprints =====')
    project = lp.projects[config['launchpad']['project']]

    url = 'https://blueprints.launchpad.net/%s/+specs?show=all' % config['launchpad']['project']
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')

    specs = soup.find_all(href=lambda x: x and re.compile('\+spec/').search(x))
    counter = 0
    for a in tqdm(specs, desc='Export blueprints'):
        name = a.get('href').split('/')[-1]

        try:
            spec = project.getSpecification(name=name)
            create_user(clean_id(spec.owner.name))
            if spec.assignee:
                create_user(clean_id(spec.assignee.name))
        except Exception as e:
            logging.exception(e)
            continue

        filename = os.path.normpath('%s/%s_blueprint.json' % (config['local']['issues'], name))
        if os.path.exists(filename):
            counter += 1
            logging.info('Blueprint %s already exists, skipping: %s' % (name, filename))
            continue

        if spec.is_complete:
            status = translate_status('Fix Released')
        elif spec.is_started and not spec.is_complete:
            status = translate_status('In Progress')
        else:
            status = translate_status('New')

        issue = {
            'externalId': name,
            'status': status,
            'reporter': spec.owner.display_name,
            'summary': spec.title,
            'description': '%s\n\n%s\n\n%s' % (spec.summary, spec.whiteboard, spec.workitems_text),
            'priority': translate_priority(spec.priority),
            'issueType': 'Story',
            'created': spec.date_created.isoformat(),
        }
        if spec.assignee:
            issue['assignee'] = spec.assignee.display_name

        export_bug['projects'][0]['issues'] = [issue]
        export_bug['links'] = []
        with open(filename, 'wb') as f:
            json.dump(export_bug, f)
        counter += 1

        logging.info('Blueprint %s export success' % name)
    logging.info('Exported blueprints: %s/%s' % (counter, len(specs)))


def main():
    logging.info('===== Export start =====')
    export_users()
    export_issues()
    export_blueprints()
    compile_export_file()
    logging.info('===== Export complete =====')


if __name__ == '__main__':
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    config.read('export.conf')

    logging.basicConfig(filename=config['logging']['filename'],
                        format=config['logging']['format'],
                        level=config['logging']['level'])

    lp = Launchpad.login_with('LP2JIRA', config['launchpad']['service'],
                              launchpadlib_dir=config['launchpad']['cache_dir'],
                              version='devel')
    user_groups = []
    if config['jira']['groups']:
        user_groups = [g.strip() for g in config['jira']['groups'].split(',')]

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
