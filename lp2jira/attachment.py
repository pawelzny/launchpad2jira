# -*- coding: utf-8 -*-
import logging
import os

from lp2jira.config import config
from lp2jira.utils import prepare_attachment_name


def create_attachments(bug):
    attachments = []
    for attachment in bug.attachments:
        f_in = attachment.data.open()
        f_name = prepare_attachment_name(f'{bug.id}_{f_in.filename}')
        filename = os.path.normpath(os.path.join(config['local']['attachments'], f_name))

        if os.path.exists(filename):
            logging.debug(f'Attachment {f_name} already exists, skipping: "{filename}"')
        else:
            with open(filename, 'wb') as f_out:
                while True:
                    buff = f_in.read(1024)
                    if buff:
                        f_out.write(buff)
                    else:
                        break
            logging.debug(f'Attachment {f_name} export success')
            attachments.append({
                'name': prepare_attachment_name(f_in.filename),
                'attacher': attachment.message.owner.name,
                'created': attachment.message.date_created.isoformat(),
                'uri': f'{config["jira"]["attachments_url"].rstrip("/")}/{f_name}'
            })
    return attachments
