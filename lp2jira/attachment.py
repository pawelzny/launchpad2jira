# -*- coding: utf-8 -*-
import logging
import os

from lp2jira.config import config
from lp2jira.utils import prepare_attachment_name, clean_id


def create_attachments(bug):
    attachments = []
    for attachment in bug.attachments:
        try:
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

                attacher = ""
                created = ""
                try:
                    attacher = clean_id(attachment.message.owner_link)
                    created = attachment.message.date_created.isoformat()
                except Exception as exc:
                    logging.warning(f"Failed details for attachment {f_name}. Attacher: {attacher}, created: {created}.")
                    logging.warning("Attachment added with default data.")
                    logging.warning(exc, exc_info=True)

                attachments.append({
                    'name': prepare_attachment_name(f_in.filename),
                    'attacher': attacher,
                    'created': created,
                    'uri': f'{config["jira"]["attachments_url"].rstrip("/")}/{f_name}'
                })
        except Exception as exc:
            logging.warning(f"Download attachment failed. Bug: {bug.id}, attachment {attachment} skipped")
            logging.warning(exc, exc_info=True)
    return attachments
