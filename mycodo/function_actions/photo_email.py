# coding=utf-8
import os
import time

from flask_babel import lazy_gettext

from mycodo.databases.models import Actions
from mycodo.databases.models import Camera
from mycodo.databases.models import SMTP
from mycodo.devices.camera import camera_record
from mycodo.function_actions.base_function_action import AbstractFunctionAction
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.function_actions import check_allowed_to_email
from mycodo.utils.send_data import send_email

FUNCTION_ACTION_INFORMATION = {
    'name_unique': 'photo_email',
    'name': 'Send Email with Photo',
    'library': None,
    'manufacturer': 'Mycodo',

    'url_manufacturer': None,
    'url_datasheet': None,
    'url_product_purchase': None,
    'url_additional': None,

    'message': 'Take a photo and send an email with it attached.',

    'usage': 'Executing <strong>self.run_action("{ACTION_ID}")</strong> will take a photo and email it to the specified recipient(s) using the SMTP credentials in the system configuration. Separate multiple recipients with commas. The body of the email will be the self-generated message. Executing <strong>self.run_action("{ACTION_ID}", value={"camera_id": "959019d1-c1fa-41fe-a554-7be3366a9c5b", "email_address": ["email1@email.com", "email2@email.com"], "message": "My message"})</strong> will capture a photo using the camera with the specified ID and send an email to the specified email(s) with message and attached photo.',

    'dependencies_module': [],

    'custom_options': [
        {
            'id': 'controller',
            'type': 'select_device',
            'default_value': '',
            'options_select': [
                'Camera'
            ],
            'name': lazy_gettext('Camera'),
            'phrase': 'Select the Camera to take a photo with'
        },
        {
            'id': 'email',
            'type': 'text',
            'default_value': 'email@domain.com',
            'required': True,
            'name': 'E-Mail Address',
            'phrase': 'E-mail recipient(s). Separate multiple with commas.'
        }
    ]
}


class ActionModule(AbstractFunctionAction):
    """Function Action: Send Email with Photo."""
    def __init__(self, action_dev, testing=False):
        super(ActionModule, self).__init__(action_dev, testing=testing, name=__name__)

        self.controller_id = None
        self.email = None

        action = db_retrieve_table_daemon(
            Actions, unique_id=self.unique_id)
        self.setup_custom_options(
            FUNCTION_ACTION_INFORMATION['custom_options'], action)

        if not testing:
            self.setup_action()

    def setup_action(self):
        self.action_setup = True

    def run_action(self, message, dict_vars):
        try:
            controller_id = dict_vars["value"]["camera_id"]
        except:
            controller_id = self.controller_id

        try:
            email_recipients = dict_vars["value"]["email_address"]
        except:
            if "," in self.email:
                email_recipients = self.email.split(",")
            else:
                email_recipients = [self.email]

        if not email_recipients:
            msg = " Error: No recipients specified."
            self.logger.error(msg)
            message += msg
            return message

        try:
            message_send = dict_vars["value"]["message"]
        except:
            message_send = None

        this_camera = db_retrieve_table_daemon(
            Camera, unique_id=controller_id, entry='first')

        if not this_camera:
            msg = " Error: Camera with ID '{}' not found.".format(controller_id)
            message += msg
            self.logger.error(msg)
            return message

        attachment_path_file = camera_record('photo', this_camera.unique_id)
        attachment_file = os.path.join(attachment_path_file[0], attachment_path_file[1])

        # If the emails per hour limit has not been exceeded
        smtp_wait_timer, allowed_to_send_notice = check_allowed_to_email()
        if allowed_to_send_notice:
            message += " Email '{email}' with photo attached.".format(
                email=",".join(email_recipients))
            if not message_send:
                message_send = message
            smtp = db_retrieve_table_daemon(SMTP, entry='first')
            send_email(smtp.host, smtp.protocol, smtp.port,
                       smtp.user, smtp.passw, smtp.email_from,
                       email_recipients, message_send,
                       attachment_file, "still")
        else:
            self.logger.error(
                "Wait {sec:.0f} seconds to email again.".format(
                    sec=smtp_wait_timer - time.time()))

        self.logger.debug("Message: {}".format(message))

        return message

    def is_setup(self):
        return self.action_setup
