# coding=utf-8
import threading

from flask_babel import lazy_gettext

from mycodo.config_translations import TRANSLATIONS
from mycodo.databases.models import Actions
from mycodo.databases.models import Output
from mycodo.function_actions.base_function_action import AbstractFunctionAction
from mycodo.utils.constraints_pass import constraints_pass_positive_or_zero_value
from mycodo.utils.database import db_retrieve_table_daemon

FUNCTION_ACTION_INFORMATION = {
    'name_unique': 'output_pwm',
    'name': '{}: {}'.format(
        TRANSLATIONS['output']['title'],
        TRANSLATIONS['duty_cycle']['title']),
    'library': None,
    'manufacturer': 'Mycodo',

    'url_manufacturer': None,
    'url_datasheet': None,
    'url_product_purchase': None,
    'url_additional': None,

    'message': lazy_gettext('Set a PWM Output to set a duty cycle.'),

    'usage': 'Executing <strong>self.run_action("{ACTION_ID}")</strong> will set the PWM output duty cycle. '
             'Executing <strong>self.run_action("{ACTION_ID}", value={"output_id": "959019d1-c1fa-41fe-a554-7be3366a9c5b", "channel": 0, "duty_cycle": 42})</strong> will set the duty cycle of the PWM output with the specified ID and channel.',

    'dependencies_module': [],

    'custom_options': [
        {
            'id': 'output',
            'type': 'select_channel',
            'default_value': '',
            'required': True,
            'options_select': [
                'Output_Channels',
            ],
            'name': 'Output',
            'phrase': 'Select an output to control'
        },
        {
            'id': 'duty_cycle',
            'type': 'float',
            'default_value': 0.0,
            'required': True,
            'constraints_pass': constraints_pass_positive_or_zero_value,
            'name': lazy_gettext('Duty Cycle'),
            'phrase': lazy_gettext('Duty cycle for the PWM (percent, 0.0 - 100.0)')
        }
    ]
}


class ActionModule(AbstractFunctionAction):
    """Function Action: Output (On/Off/Duration)."""
    def __init__(self, action_dev, testing=False):
        super(ActionModule, self).__init__(action_dev, testing=testing, name=__name__)

        self.output_device_id = None
        self.output_channel_id = None
        self.duty_cycle = None

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
            output_id = dict_vars["value"]["output_id"]
        except:
            output_id = self.output_device_id

        try:
            output_channel = dict_vars["value"]["channel"]
        except:
            output_channel = self.get_output_channel_from_channel_id(
                self.output_channel_id)

        try:
            duty_cycle = dict_vars["value"]["duty_cycle"]
        except:
            duty_cycle = self.duty_cycle

        this_output = db_retrieve_table_daemon(
            Output, unique_id=output_id, entry='first')

        if not this_output:
            msg = " Error: Output with ID '{}' not found.".format(this_output)
            message += msg
            self.logger.error(msg)
            return message

        message += " Set output {unique_id} CH{ch} ({id}, {name}) duty cycle to {duty_cycle} %.".format(
            unique_id=output_id,
            ch=output_channel,
            id=this_output.id,
            name=this_output.name,
            duty_cycle=duty_cycle)

        output_on = threading.Thread(
            target=self.control.output_on,
            args=(output_id,),
            kwargs={'output_type': 'pwm',
                    'amount': duty_cycle,
                    'output_channel': output_channel})
        output_on.start()

        self.logger.debug("Message: {}".format(message))

        return message

    def is_setup(self):
        return self.action_setup
