import struct
import logging
import re
from copy import deepcopy
from abc import ABC

logger = logging.getLogger(__name__)


class MessageABC(ABC):

    # The length of the message. Should be overwritten in child class
    msg_length = 0

    # The message command code. Should be overwritten in child class
    command_code = 0x00

    # Template that is specific to each message type. Should be overwritten in child class
    msg_specific_template = {}

    # Base message template that is common for all messages
    base_template = {
        'header': {
            'format': '<Q',
            'start_byte': 0,
            'value': 0x11DDDDDDDDDDDDDD
        },
        'msg_length': {
            'format': '<L',
            'start_byte': 8,
            'value': 0
        },
        'command_code': {
            'format': '<L',
            'start_byte': 12,
            'value': 0x00000000
        },
        'extended_command_code': {
            'format': '<L',
            'start_byte': 16,
            'value': 0x00000000
        },
    }

    @classmethod
    def unpack(cls, msg_bin: bytearray) -> dict:
        """
        Parses the passed message and decodes it with the msg_encoding dict.
        Each key in the output message will have name of the key from the 
        msg_encoding dictionary.

        Parameters
        ----------
        msg_bin : bytearry
            The message to unpack.

        Returns
        -------
        decoded_msg_dict : dict
            The message items decoded into a dictionary.
        """
        decoded_msg_dict = {}

        # Create a template to unpack message with
        template = {**deepcopy(cls.base_template),
                    **deepcopy(cls.msg_specific_template)}

        for item_name, item in template.items():
            start_idx = item['start_byte']
            end_idx = item['start_byte'] + struct.calcsize(item['format'])
            decoded_msg_dict[item_name] = struct.unpack(
                item['format'], msg_bin[start_idx:end_idx])[0]

            # Decode and strip trailing 0x00s from strings.
            if item['format'].endswith('s'):
                # ignore utf-8 characters that cannot be decoded
                if item['text_encoding'] == 'utf-8':
                    decoded_msg_dict[item_name] = decoded_msg_dict[item_name].decode(
                        item['text_encoding'], errors='ignore').rstrip('\x00')
                else:
                    decoded_msg_dict[item_name] = decoded_msg_dict[item_name].decode(
                        item['text_encoding']).rstrip('\x00')

        if decoded_msg_dict['command_code'] != cls.command_code:
            logger.warning(
                f'Decoded command code {decoded_msg_dict["command_code"]} does not match what was expected!')

        if decoded_msg_dict['msg_length'] != cls.msg_length:
            logger.warning(
                f'Decoded message length {decoded_msg_dict["msg_length"]} does not match what was expected!')

        return decoded_msg_dict

    @classmethod
    def pack(cls, msg_values={}) -> bytearray:
        """
        Packs a message based on the message encoding given in the msg_specific_template
        dictionary. Values can be substituted for default values if they are included 
        in the `msg_values` argument.

        Parameters
        ----------
        msg_values : dict
            A dictionary detailing which default values in the message temple should be 
            updated.

        Returns
        -------
        msg_bin : bytearray
            Packed response message.
        """
        # Create a template to build messages from
        template = {**deepcopy(cls.base_template),
                    **deepcopy(cls.msg_specific_template)}

        # Update the template with message specific length and command code
        template['msg_length']['value'] = cls.msg_length
        template['command_code']['value'] = cls.command_code

        # Create a message bytearray that will be loaded with message contents
        msg_bin = bytearray(template['msg_length']['value'])

        # Update default message values with those in the passed msg_values dict
        for key in msg_values.keys():
            if key in template.keys():
                template[key]['value'] = msg_values[key]
            else:
                logger.warning(
                    f'Key name {key} was not found in msg_encoding!')

        # Pack each item in template. If packing any item fails then abort packing.
        for item_name, item in template.items():
            logger.debug(f'Packing item {item_name}')
            try:
                if item['format'].endswith('s') or item['format'].endswith('c'):
                    packed_item = struct.pack(
                        item['format'],
                        item['value'].encode(item['text_encoding']))
                else:
                    packed_item = struct.pack(
                        item['format'], item['value'])
            except struct.error as e:
                logger.error(
                    f'Error packing {item_name} with fields {item}!')
                logger.error(e)
                msg_bin = bytearray([])
                break

            start_idx = item['start_byte']
            end_idx = item['start_byte'] + struct.calcsize(item['format'])
            msg_bin[start_idx:end_idx] = packed_item

        # Append a checksum to the end of the message
        if msg_bin:
            msg_bin += struct.pack('<H', sum(msg_bin))

        return msg_bin


class Msg:
    class Login:
        '''
        Message for logging into Arbin cycler. See
        CTI_REQUEST_LOGIN/CTI_REQUEST_LOGIN_FEEDBACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 74
            command_code = 0xEEAB0001

            msg_specific_template = {
                'username': {
                    'format': '32s',
                    'start_byte': 20,
                    'text_encoding': 'utf-8',
                    'value': 'not a username'
                },
                'password': {
                    'format': '32s',
                    'start_byte': 52,
                    'text_encoding': 'utf-8',
                    'value': 'not a password'
                },
            }

        class Server(MessageABC):
            msg_length = 8678
            command_code = 0xEEBA0001

            msg_specific_template = {
                'result': {
                    'format': 'I',
                    'start_byte': 20,
                    'value': 1
                },
                'ip_address': {
                    'format': '4s',
                    'start_byte': 24,
                    'value': "0000",
                    'text_encoding': 'utf-8',
                },
                'cycler_sn': {
                    'format': '16s',
                    'start_byte': 28,
                    'value': '00000000',
                    'text_encoding': 'ascii',
                },
                'note': {
                    'format': '256s',
                    'start_byte': 44,
                    'value': '00000000',
                    'text_encoding': 'ascii',
                },
                'nick_name': {
                    # Stored as wchar_t[1024]. Each wchar_t is 2 bytes, twice as big as standard char in Python
                    'format': '2048s',
                    'start_byte': 300,
                    'value': 'our nickname',
                    'text_encoding': 'utf-16-le',
                },
                'location': {
                    'format': '2048s',
                    'start_byte': 2348,
                    'value': 'our location',
                    'text_encoding': 'utf-16-le',
                },
                'emergency_contact': {
                    'format': '2048s',
                    'start_byte': 4396,
                    'value': 'our location',
                    'text_encoding': 'utf-16-le',
                },
                'other_comments': {
                    'format': '2048s',
                    'start_byte': 6444,
                    'value': 'our location',
                    'text_encoding': 'utf-16-le',
                },
                'email': {
                    'format': '128s',
                    'start_byte': 8492,
                    'value': 'our location',
                    'text_encoding': 'utf-16-le',
                },
                'call': {
                    'format': '32s',
                    'start_byte': 8620,
                    'value': 'our location',
                    'text_encoding': 'utf-16-le',
                },
                'itac': {
                    'format': '<I',
                    'start_byte': 8652,
                    'value': 0
                },
                'version': {
                    'format': '<I',
                    'start_byte': 8656,
                    'value': 0
                },
                'allow_control': {
                    'format': '<I',
                    'start_byte': 8660,
                    'value': 0
                },
                'num_channels': {
                    'format': '<I',
                    'start_byte': 8664,
                    'value': 0
                },
                'user_type': {
                    'format': '<I',
                    'start_byte': 8668,
                    'value': 1,
                    'text_encoding': 'utf-16-le',
                },
                'picture_length': {
                    'format': '<I',
                    'start_byte': 8672,
                    'value': 0,
                    'text_encoding': 'utf-8',
                },
            }

            login_result_dict = {
                0: "should not see this",
                1: "success",
                2: "fail",
                3: "already logged in"
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but converts the result based on the
                login_result_dict.

                Parameters
                ----------
                msg_bin : bytearray
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)
                msg_dict['result'] = cls.login_result_dict[msg_dict['result']]
                return msg_dict

    class ChannelInfo:
        '''
        Message for getting channel info from cycler. See
        CTI_REQUEST_GET_CHANNELS_INFO/CTI_REQUEST_GET_CHANNELS_INFO_FEED_BACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 50
            command_code = 0xEEAB0003

            msg_specific_template = {
                'channel': {
                    'format': '<h',
                    'start_byte': 20,
                    'value': 0
                },
                'channel_selection': {
                    'format': '<h',
                    'start_byte': 22,
                    'value': 1
                },
                'aux_options': {
                    'format': '<I',
                    'start_byte': 24,
                    'value': 0x00
                },
                'reserved': {
                    'format': '32s',
                    'start_byte': 28,
                    'value': ''.join(['\0' for i in range(32)]),
                    'text_encoding': 'utf-8',
                },
            }

        class Server(MessageABC):

            # Default message length for 1 channel with no aux readings. Will be larger as those grow.
            msg_length = 1779
            command_code = 0xEEBA0003

            msg_specific_template = {
                'number_of_channels': {
                    'format': '<I',
                    'start_byte': 20,
                    'value': 1
                },
                'channel': {
                    'format': '<I',
                    'start_byte': 24,
                    'value': 0
                },
                'status': {
                    'format': '<h',
                    'start_byte': 28,
                    'value': 0x00
                },
                'comm_failure': {
                    'format': '<B',
                    'start_byte': 30,
                    'value': 0
                },
                'schedule': {
                    # Stored as wchar_t[200]. Each wchar_t is 2 bytes, twice as big as standard char in Python
                    'format': '400s',
                    'start_byte': 31,
                    'value': 'fake_schedule',
                    'text_encoding': 'utf-16-le',
                },
                'testname': {
                    # Stored as wchar_t[72]
                    'format': '144s',
                    'start_byte': 431,
                    'value': 'fake_testname',
                    'text_encoding': 'utf-16-le',
                },
                'exit_condition': {
                    'format': '100s',
                    'start_byte': 575,
                    'value': 'none',
                    'text_encoding': 'utf-8',
                },
                'step_and_cycle_format': {
                    'format': '64s',
                    'start_byte': 675,
                    'value': 'none',
                    'text_encoding': 'utf-8',
                },
                # Stored as wchar_t[72]
                'barcode': {
                    'format': '144s',
                    'start_byte': 739,
                    'value': 'none',
                    'text_encoding': 'utf-16',
                },
                # Stored as wchar_t[72]
                'can_config_name': {
                    'format': '400s',
                    'start_byte': 883,
                    'value': 'none',
                    'text_encoding': 'utf-16',
                },
                # Stored as wchar_t[72]
                'smb_config_name': {
                    'format': '400s',
                    'start_byte': 1283,
                    'value': 'none',
                    'text_encoding': 'utf-16',
                },
                'master_channel': {
                    'format': '<H',
                    'start_byte': 1683,
                    'value': 0,
                },
                'test_time_s': {
                    'format': '<d',
                    'start_byte': 1685,
                    'value': 0,
                },
                'step_time_s': {
                    'format': '<d',
                    'start_byte': 1693,
                    'value': 0,
                },
                'voltage_v': {
                    'format': '<f',
                    'start_byte': 1701,
                    'value': 0,
                },
                'current_a': {
                    'format': '<f',
                    'start_byte': 1705,
                    'value': 0,
                },
                'power_w': {
                    'format': '<f',
                    'start_byte': 1709,
                    'value': 0,
                },
                'charge_capacity_ah': {
                    'format': '<f',
                    'start_byte': 1713,
                    'value': 0,
                },
                'discharge_capacity_ah': {
                    'format': '<f',
                    'start_byte': 1717,
                    'value': 0,
                },
                'charge_energy_wh': {
                    'format': '<f',
                    'start_byte': 1721,
                    'value': 0,
                },
                'discharge_energy_wh': {
                    'format': '<f',
                    'start_byte': 1725,
                    'value': 0,
                },
                'internal_resistance_ohm': {
                    'format': '<f',
                    'start_byte': 1729,
                    'value': 0,
                },
                'dvdt_vbys': {
                    'format': '<f',
                    'start_byte': 1733,
                    'value': 0,
                },
                'acr_ohm': {
                    'format': '<f',
                    'start_byte': 1737,
                    'value': 0,
                },
                'aci_ohm': {
                    'format': '<f',
                    'start_byte': 1741,
                    'value': 0,
                },
                'aci_phase_degrees': {
                    'format': '<f',
                    'start_byte': 1745,
                    'value': 0,
                },
                'aux_voltage_count': {
                    'format': '<H',
                    'start_byte': 1749,
                    'value': 0,
                },
                'aux_temperature_count': {
                    'format': '<H',
                    'start_byte': 1751,
                    'value': 0,
                },
                'aux_pressure_count': {
                    'format': '<H',
                    'start_byte': 1753,
                    'value': 0,
                },
                'aux_external_count': {
                    'format': '<H',
                    'start_byte': 1755,
                    'value': 0,
                },
                'aux_flow_count': {
                    'format': '<H',
                    'start_byte': 1757,
                    'value': 0,
                },
                'aux_ao_count': {
                    'format': '<H',
                    'start_byte': 1759,
                    'value': 0,
                },
                'aux_di_count': {
                    'format': '<H',
                    'start_byte': 1761,
                    'value': 0,
                },
                'aux_do_count': {
                    'format': '<H',
                    'start_byte': 1763,
                    'value': 0,
                },
                'aux_humidity_count': {
                    'format': '<H',
                    'start_byte': 1765,
                    'value': 0,
                },
                'aux_safety_count': {
                    'format': '<H',
                    'start_byte': 1767,
                    'value': 0,
                },
                'aux_ph_count': {
                    'format': '<H',
                    'start_byte': 1769,
                    'value': 0,
                },
                'aux_density_count': {
                    'format': '<H',
                    'start_byte': 1771,
                    'value': 0,
                },
                'bms_count': {
                    'format': '<H',
                    'start_byte': 1773,
                    'value': 0,
                },
                'smb_count': {
                    'format': '<H',
                    'start_byte': 1775,
                    'value': 0,
                },
            }

            # List of staus codes. Each index in the corresponding status code.
            status_code_dict = {
                0: 'Idle',
                1: 'Transition',
                2: 'Charge',
                3: 'Discharge',
                4: 'Rest',
                5: 'Wait',
                6: 'External Charge',
                7: 'Calibration',
                8: 'Unsafe',
                9: 'Pulse',
                10: 'Internal Resistance',
                11: 'AC Impedance',
                12: 'ACI Cell',
                13: 'Test Settings',
                14: 'Error',
                15: 'Finished',
                16: 'Volt Meter',
                17: 'Waiting for ACS',
                18: 'Pause',
                19: 'Empty',
                20: 'Idle from MCU',
                21: 'Start',
                22: 'Running',
                23: 'Step Transfer',
                24: 'Resume',
                25: 'Go Pause',
                26: 'Go Stop',
                27: 'Go Next Step',
                28: 'Online Update',
                29: 'DAQ Memory Unsafe',
                30: 'ACR'
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but uses aux counts to unpack aux readings

                Parameters
                ----------
                msg_bin : bytearry
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)
                msg_dict = cls.aux_readings_parser(
                    msg_dict, msg_bin, starting_aux_idx=1777)
                msg_dict['status'] = cls.status_code_dict[msg_dict['status']]
                return msg_dict

            @classmethod
            def pack(cls, msg_values={}) -> bytearray:
                """
                Same as parent method, but handles packing aux measurements.

                Parameters
                ----------
                msg_values : dict
                    A dictionary detailing which default values in the message temple should be 
                    updated.

                Returns
                -------
                msg : bytearray
                    Packed response message.
                """
                # TODO : Modify so that we can aux values can be packed.
                msg_bin = super().pack(msg_values)
                return msg_bin

            @classmethod
            def aux_readings_parser(cls, msg_dict: dict, msg_bin: bytearray, starting_aux_idx=1777):
                """
                Parses the auxiliary readings in msg_bin based on the aux readings
                counts in msg_dict. Aux readings are then added as items to the msg_dict. 

                Parameters
                ----------
                msg_dict : dict
                    A dictionary containing the aux readings counts (aux_voltage_count, aux_voltage_count, etc)
                msg_bin : bytearray
                    The message to unpack as a byte array.
                starting_aux_idx : int
                    The starting index in the msg_bin for aux readings. 1777 in single channel messages

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                aux_lists = []

                aux_count_name_list = [
                    'aux_voltage_count',
                    'aux_temperature_count',
                    'aux_pressure_count',
                    'aux_external_count',
                    'aux_flow_count',
                    'aux_ao_count',
                    'aux_di_count',
                    'aux_do_count',
                    'aux_humidity_count',
                    'aux_safety_count',
                    'aux_ph_count',
                    'aux_density_count'
                ]

                # Generate a list of readings for each aux reading.
                # If count is non-zero then genreate a aux_reading and aux_reading_dt list of that length
                # Else, generate empty lists for the aux_reading and aux_reading_dt
                for aux_count_name in aux_count_name_list:
                    aux_reading_name = re.split('_count', aux_count_name)[0]
                    aux_dt_name = aux_reading_name + '_dt'
                    if msg_dict[aux_count_name]:
                        msg_dict[aux_reading_name] = [0 for x in range(
                            msg_dict[aux_count_name])]
                        msg_dict[aux_dt_name] = [0 for x in range(
                            msg_dict[aux_count_name])]
                        aux_lists.append(
                            [msg_dict[aux_reading_name], msg_dict[aux_dt_name]])
                    else:
                        msg_dict[aux_reading_name] = []
                        msg_dict[aux_dt_name] = []

                # For aux readings that have a measurements, add them to the respective reading list.
                current_aux_idx = starting_aux_idx
                for readings_list in aux_lists:
                    for i in range(0, len(readings_list[0])):
                        # The first list in reading list is reading itself
                        readings_list[0][i] = struct.unpack(
                            '<f', msg_bin[current_aux_idx:current_aux_idx+4])[0]
                        # The second reading in the list is the dt value.
                        readings_list[1][i] = struct.unpack(
                            '<f', msg_bin[current_aux_idx+4:current_aux_idx+8])[0]
                        current_aux_idx += 8

                return msg_dict

    class AssignSchedule:
        '''
        Message for assiging a schedule to a specific channel. See
        THIRD_PARTY_ASSIGN_SCHEDULE/THIRD_PARTY_ASSIGN_SCHEDULE_FEEDBACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 659
            command_code = 0xBB210001

            msg_specific_template = {
                'channel': {
                    'format': 'i',
                    'start_byte': 20,
                    'value': 0
                },
                # Always 0x00 for PyCTI-Arbin since we only work with single channels
                'assign_all_channels': {
                    'format': '1s',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'schedule': {
                    # Stored as wchar_t[200]. Each wchar_t is 2 bytes, twice as big as standard char in Python
                    'format': '400s',
                    'start_byte': 25,
                    'value': 'fake_schedule',
                    'text_encoding': 'utf-16-le',
                },
                'test_capacity_ah': {
                    'format': '<f',
                    'start_byte': 425,
                    'value': 1.0,
                },
                'barcode': {
                    'format': '144s',
                    'start_byte': 429,
                    'value': '',
                    'text_encoding': 'utf-16-le',
                },
                'user_variable_1': {
                    'format': '<f',
                    'start_byte': 573,
                    'value': 1.0,
                },
                'user_variable_2': {
                    'format': '<f',
                    'start_byte': 577,
                    'value': 1.0,
                },
                'user_variable_3': {
                    'format': '<f',
                    'start_byte': 581,
                    'value': 1.0,
                },
                'user_variable_4': {
                    'format': '<f',
                    'start_byte': 585,
                    'value': 1.0,
                },
                'user_variable_5': {
                    'format': '<f',
                    'start_byte': 589,
                    'value': 1.0,
                },
                'user_variable_6': {
                    'format': '<f',
                    'start_byte': 593,
                    'value': 1.0,
                },
                'user_variable_7': {
                    'format': '<f',
                    'start_byte': 597,
                    'value': 1.0,
                },
                'user_variable_8': {
                    'format': '<f',
                    'start_byte': 601,
                    'value': 1.0,
                },
                'user_variable_9': {
                    'format': '<f',
                    'start_byte': 605,
                    'value': 1.0,
                },
                'user_variable_10': {
                    'format': '<f',
                    'start_byte': 609,
                    'value': 1.0,
                },
                'user_variable_11': {
                    'format': '<f',
                    'start_byte': 613,
                    'value': 1.0,
                },
                'user_variable_12': {
                    'format': '<f',
                    'start_byte': 617,
                    'value': 1.0,
                },
                'user_variable_13': {
                    'format': '<f',
                    'start_byte': 621,
                    'value': 1.0,
                },
                'user_variable_14': {
                    'format': '<f',
                    'start_byte': 625,
                    'value': 1.0,
                },
                'user_variable_15': {
                    'format': '<f',
                    'start_byte': 629,
                    'value': 1.0,
                },
                'user_variable_16': {
                    'format': '<f',
                    'start_byte': 633,
                    'value': 1.0,
                },
                'reserved': {
                    'format': '32s',
                    'start_byte': 637,
                    'value': ''.join(['\0' for i in range(32)]),
                    'text_encoding': 'utf-8',
                },
            }

        class Server(MessageABC):
            msg_length = 128
            command_code = 0xBB120001

            msg_specific_template = {
                'channel': {
                    'format': 'i',
                    'start_byte': 20,
                    'value': 0
                },
                'result': {
                    'format': 'c',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 25,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

            assign_schedule_feedback_codes = {
                0: 'success',
                16: 'channel does not exist',
                17: 'Monitor window in use at the moment',
                18: 'Schedule name cannot be empty',
                19: 'Schedule name not found',
                20: 'Channel is running',
                21: 'Channel is downloading another schedule currently',
                22: 'Cannot assign schedule when batch file is open',
                23: 'Assign failed',
                24: 'Not used: User should never see this',
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but converts the result based on the
                assign_schedule_feedback_codes.

                Parameters
                ----------
                msg_bin : bytearray
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)
                msg_dict['result'] = cls.assign_schedule_feedback_codes[
                    ord(msg_dict['result'])]
                return msg_dict

    class StartSchedule:
        '''
        Message for assigning a schedule to a specific channel. See
        THIRD_PARTY_START_SCHEDULE/THIRD_PARTY_START_SCHEDULE_FEEDBACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 160
            command_code = 0xBB320004

            msg_specific_template = {
                'test_name': {
                    # Read as wchar_t which has length of 2 bytes each.
                    'format': '144s',
                    'start_byte': 20,
                    'value': 'pycti-arbin test name',
                    'text_encoding': 'utf-16-le',
                },
                'num_channels_to_start': {
                    'format': '<I',
                    'start_byte': 164,
                    'value': 1
                },
                'channel': {
                    'format': '<H',
                    'start_byte': 168,
                    'value': 0
                },
            }

        class Server(MessageABC):
            msg_length = 128
            command_code = 0XBB230004

            msg_specific_template = {
                'channel': {
                    'format': 'I',
                    'start_byte': 20,
                    'value': 0
                },
                'result': {
                    'format': 'c',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 25,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

            start_test_feedback_codes = {
                0: 'success',
                16: 'Invalid channel index',
                17: 'There is a user controlling the monitor window (Start/Resume channel window is open)',
                18: 'Requested channel is running or unsafe',
                19: 'Channel not connected to DAQ',
                20: 'Schedule not compatible with current system configuration',
                21: 'No schedule assigned to channel',
                22: 'Schedule version does not match current version of MITS',
                23: 'Not used: User should never see this',
                24: 'Not used: User should never see this',
                25: 'Invalid step number',
                26: 'Not used: User should never see this',
                27: 'Invalid auxiliary count in schedule',
                28: 'Invalid build in auxiliary count',
                29: 'Not used: User should never see this',
                30: 'Check Aux Test Setting tab',
                31: 'No selected channels',
                32: 'Not used: User should never see this',
                33: 'DAQ still downloading schedule',
                34: 'Error querying database (database connection closed most likely)',
                35: 'Testname cannot be empty',
                36: 'Invalid step number',
                37: 'Invalid parallel channel number',
                38: 'Schedule safety precheck failed',
                39: 'Not used: User should never see this',
                40: 'Battery simulation error',
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but converts the result based on the
                start_test_feedback_codes.

                Parameters
                ----------
                msg_bin : bytearray
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)
                msg_dict['result'] = cls.start_test_feedback_codes[
                    ord(msg_dict['result'])]
                return msg_dict

    class StopSchedule:
        '''
        Message for stopping a test on a specific channel. See
        THIRD_PARTY_STOP_SCHEDULE/THIRD_PARTY_STOP_SCHEDULE_FEEDBACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 116
            command_code = 0xBB310001

            msg_specific_template = {
                'channel': {
                    'format': 'I',
                    'start_byte': 20,
                    'value': 0
                },
                # Always 0x00, others all channels are stopped.
                'stop_all_channels': {
                    'format': '1s',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 25,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

        class Server(MessageABC):
            msg_length = 128
            command_code = 0XBB130001

            msg_specific_template = {
                'channel': {
                    'format': 'I',
                    'start_byte': 20,
                    'value': 0
                },
                'result': {
                    'format': 'c',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 25,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

            stop_test_feedback_codes = {
                0: 'success',
                16: 'Channel index does not exist',
                17: 'Someone else is controlling monitor window at the moment',
                18: 'Not used: User should never see this',
                19: 'Not used: User should never see this',
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but converts the result based on the
                stop_test_feedback_codes.

                Parameters
                ----------
                msg_bin : bytearray
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)
                msg_dict['result'] = cls.stop_test_feedback_codes[
                    ord(msg_dict['result'])]
                return msg_dict

    class JumpChannel:
        '''
        Message for jumping channel to a different step in its schedule file.
        THIRD_PARTY_JUMP_CHANNEL/THIRD_PARTY_JUMP_CHANNEL_FEEDBACK
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 119
            command_code = 0xBB320005

            msg_specific_template = {
                'step_num': {
                    'format': '<L',
                    'start_byte': 20,
                    'value': 0,
                },
                'channel': {
                    'format': '<L',
                    'start_byte': 24,
                    'value': 0
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 28,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

        class Server(MessageABC):
            msg_length = 128
            command_code = 0xBB230005

            msg_specific_template = {
                'channel': {
                    'format': '<I',
                    'start_byte': 20,
                    'value': 0
                },
                'result': {
                    'format': 'c',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 25,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

            jump_channel_feedback_codes = {
                0: 'success',
                17: 'Someone else is using the monitor window at the moment',
                18: 'Channel not running',
                19: 'Channel not connected to DAQ',
                20: 'Invalid Schedule',
                21: 'No schedule assigned',
                22: 'Invalid schedule version',
                25: 'Schedule cannot contain over 200 steps',
                33: 'DAQ still downloading schedule',
                36: 'Schedule contains invalid step limit setting',
                37: 'Invalid parallel setting',
                38: 'Schedule safety check not safe',
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but converts the result based on the
                jump_channel_feedback_codes.

                Parameters
                ----------
                msg_bin : bytearray
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)
                msg_dict['result'] = cls.jump_channel_feedback_codes[
                    ord(msg_dict['result'])]
                return msg_dict

    class SetMetaVariable:
        '''
        Message for setting meta variables. 
        THIRD_PARTY_SET_MV_VALUE/THIRD_PARTY_SET_MV_VALUE_FEEDBACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 62
            command_code = 0xBB150001

            msg_specific_template = {
                'channel': {
                    'format': '<I',
                    'start_byte': 20,
                    'value': 0
                },
                # The only mv_type allowed for CTI is 1
                'mv_type': {
                    'format': '<i',
                    'start_byte': 24,
                    'value': 1
                },
                # This determines which meta variable is set. Defaults to MV 1.
                'mv_meta_code': {
                    'format': '<i',
                    'start_byte': 28,
                    'value': 52,
                },
                'reserved_1': {
                    'format': '16s',
                    'start_byte': 32,
                    'value': ''.join(['\0' for i in range(16)]),
                    'text_encoding': 'utf-8',
                },
                # The only value type allowed for CTI is 1, float.
                'mv_value_type': {
                    'format': '<i',
                    'start_byte': 48,
                    'value': 1
                },
                'mv_data': {
                    'format': '<f',
                    'start_byte': 52,
                    'value': 1
                },
                'reserved_2': {
                    'format': '16s',
                    'start_byte': 56,
                    'value': ''.join(['\0' for i in range(16)]),
                    'text_encoding': 'utf-8',
                },
            }

            # Specifies the code for each variable. E.g. MV_UD1 has a code of 52
            mv_channel_codes = {
                1: 52,
                2: 53,
                3: 54,
                4: 55,
                5: 105,
                6: 106,
                7: 107,
                8: 108,
                9: 109,
                10: 110,
                11: 111,
                12: 112,
                13: 113,
                14: 114,
                15: 115,
                16: 116,
            }

        class Server(MessageABC):
            msg_length = 128
            command_code = 0XBB510001

            msg_specific_template = {
                'channel': {
                    'format': '<I',
                    'start_byte': 20,
                    'value': 0
                },
                'result': {
                    'format': 'c',
                    'start_byte': 24,
                    'value': '\0',
                    'text_encoding': 'utf-8',
                },
                'reserved': {
                    'format': '101s',
                    'start_byte': 25,
                    'value': ''.join(['\0' for i in range(101)]),
                    'text_encoding': 'utf-8',
                },
            }

            mv_result_decoder = {
                0: 'success',
                16: 'Set MV Failure',
                17: 'Channel is not running',
                18: 'Meta code does not exist'
            }

            @classmethod
            def unpack(cls, msg_bin: bytearray) -> dict:
                """
                Same as the parent method, but converts the result based on the
                stop_test_feedback_codes.

                Parameters
                ----------
                msg_bin : bytearry
                    The message to unpack.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().unpack(msg_bin)

                # Convert the result code to a string
                result = ord(msg_dict['result'])
                if result not in cls.mv_result_decoder.keys():
                    logger.warning(
                        f'Unknown result code {result} for SetMetaVariable message!')
                    msg_dict['result'] = 'Unknown'
                else:
                    msg_dict['result'] = cls.mv_result_decoder[result]

                return msg_dict
