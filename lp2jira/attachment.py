# -*- coding: utf-8 -*-
import logging
import os

from lp2jira.config import config


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
