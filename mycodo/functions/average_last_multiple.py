# coding=utf-8
#
#  average_last_multiple.py - Calculates the average of last measurements for multiple channels
#
#  Copyright (C) 2015-2020 Kyle T. Gabriel <mycodo@kylegabriel.com>
#
#  This file is part of Mycodo
#
#  Mycodo is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mycodo is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mycodo. If not, see <http://www.gnu.org/licenses/>.
#
#  Contact at kylegabriel.com
#
import threading
import time

from flask_babel import lazy_gettext

from mycodo.controllers.base_controller import AbstractController
from mycodo.databases.models import Conversion
from mycodo.databases.models import CustomController
from mycodo.mycodo_client import DaemonControl
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.influx import add_measurements_influxdb
from mycodo.utils.influx import read_last_influxdb
from mycodo.utils.system_pi import get_measurement
from mycodo.utils.system_pi import return_measurement_info


def constraints_pass_positive_value(mod_controller, value):
    """
    Check if the user controller is acceptable
    :param mod_controller: SQL object with user-saved Input options
    :param value: float or int
    :return: tuple: (bool, list of strings)
    """
    errors = []
    all_passed = True
    # Ensure value is positive
    if value <= 0:
        all_passed = False
        errors.append("Must be a positive value")
    return all_passed, errors, mod_controller


measurements_dict = {
    0: {
        'measurement': '',
        'unit': '',
    }
}

FUNCTION_INFORMATION = {
    'function_name_unique': 'average_last_multiple',
    'function_name': 'Function: Average (Last, Multiple)',
    'measurements_dict': measurements_dict,
    'enable_channel_unit_select': True,

    'message': 'This function acquires the last measurement of those that are selected, averages them, then stores the resulting value as the selected measurement and unit.',

    'options_enabled': [
        'measurements_select_measurement_unit',
        'custom_options'
    ],

    'custom_options': [
        {
            'id': 'period',
            'type': 'float',
            'default_value': 60,
            'required': True,
            'constraints_pass': constraints_pass_positive_value,
            'name': lazy_gettext('Period (seconds)'),
            'phrase': lazy_gettext('The duration (seconds) between measurements or actions')
        },
        {
            'id': 'start_offset',
            'type': 'integer',
            'default_value': 10,
            'required': True,
            'name': 'Start Offset',
            'phrase': 'The duration (seconds) to wait before the first operation'
        },
        {
            'id': 'max_measure_age',
            'type': 'integer',
            'default_value': 360,
            'required': True,
            'name': 'Measurement Max Age',
            'phrase': 'The maximum allowed age of the measurement'
        },
        {
            'id': 'select_measurement',
            'type': 'select_multi_measurement',
            'default_value': '',
            'options_select': [
                'Input',
                'Math',
                'Function'
            ],
            'name': 'Measurement',
            'phrase': 'Measurement to replace "x" in the equation'
        }
    ]
}


class CustomModule(AbstractController, threading.Thread):
    """
    Class to operate custom controller
    """
    def __init__(self, ready, unique_id, testing=False):
        threading.Thread.__init__(self)
        super(CustomModule, self).__init__(ready, unique_id=unique_id, name=__name__)

        self.unique_id = unique_id
        self.log_level_debug = None
        self.timer_loop = time.time()

        self.control = DaemonControl()

        # Initialize custom options
        self.period = None
        self.start_offset = None
        self.select_measurement = None
        self.max_measure_age = None

        # Set custom options
        custom_function = db_retrieve_table_daemon(
            CustomController, unique_id=unique_id)
        self.setup_custom_options(
            FUNCTION_INFORMATION['custom_options'], custom_function)

    def initialize_variables(self):
        controller = db_retrieve_table_daemon(
            CustomController, unique_id=self.unique_id)
        self.log_level_debug = controller.log_level_debug
        self.set_log_level_debug(self.log_level_debug)

    def loop(self):
        if self.timer_loop < time.time():
            while self.timer_loop < time.time():
                self.timer_loop += self.period

            measurements = []
            for each_id_set in self.select_measurement:
                device_device_id = each_id_set.split(",")[0]
                device_measure_id = each_id_set.split(",")[1]

                device_measurement = get_measurement(device_measure_id)

                if not device_measurement:
                    self.logger.error("Could not find Device Measurement")
                    return

                conversion = db_retrieve_table_daemon(
                    Conversion, unique_id=device_measurement.conversion_id)
                channel, unit, measurement = return_measurement_info(
                    device_measurement, conversion)

                last_measurement = read_last_influxdb(
                    device_device_id,
                    unit,
                    channel,
                    measure=measurement,
                    duration_sec=self.max_measure_age)

                if not last_measurement:
                    self.logger.error("Could not find measurement within the set Max Age")
                    return False
                else:
                    measurements.append(last_measurement[1])

            average = float(sum(measurements) / float(len(measurements)))

            measurement_dict = {
                0: {
                    'measurement': self.channels_measurement[0].measurement,
                    'unit': self.channels_measurement[0].unit,
                    'value': average
                }
            }

            if measurement_dict:
                self.logger.debug(
                    "Adding measurements to InfluxDB with ID {}: {}".format(
                        self.unique_id, measurement_dict))
                add_measurements_influxdb(self.unique_id, measurement_dict)
            else:
                self.logger.debug(
                    "No measurements to add to InfluxDB with ID {}".format(
                        self.unique_id))
