import logging
import os
from typing import Optional, Literal, Dict
from pydantic import BaseModel, validator
from .messages import Msg

from .cycler_interface import CyclerInterface

logger = logging.getLogger(__name__)


class ChannelInterface(CyclerInterface):
    """
    Class for controlling Maccor Cycler using MacNet.
    """

    def __init__(self, config: dict, env_path: str = os.path.join(os.getcwd(), '.env')):
        """
        A class for interfacing with the Arbin cycler.

        Parameters
        ----------
        config : dict
            A configuration dictionary. Must contain the following keys:s
            - `ip_address` - The IP address of the Maccor server. Use 127.0.0.1 if running on the same machine as the server.
            - `port` - The port to communicate through with JSON messages. Default set to 57570.
            - `timeout_s` - *optional* - How long to wait before timing out on TCP communication. Defaults to 2 seconds. 
            - `msg_buffer_size_bytes` - *optional* - How big of a message buffer to use for sending/receiving messages. 
               A minimum of 1024 bytes is recommended. Defaults to 4096 bytes. 
        env_path : *optional* : str
            The path to the `.env` file containing the Arbin CTI username,`ARBIN_CTI_USERNAME`, and password, `ARBIN_CTI_PASSWORD`.
            Defaults to looking in the working directory.
        """

       # Validate and create a config container class
        self.__config = ChannelInterfaceConfig(**config)

        self.__assign_schedule_feedback = {}
        self.__start_test_feedback = {}
        self.__stop_test_feedback = {}

        super().__init__(self.__config.dict(), env_path)

    def read_status(self) -> dict:
        """
        Method to read the status of the channel defined in the config.

        Returns
        -------
        status : dict
            A dictionary detailing the status of the channel. Returns None if there is an issue.
        """
        return self.read_channel_status(channel=self.__config.channel)

    def assign_schedule(self) -> bool:
        """
        Method to assign a schedule to the channel defined in the config.

        Returns
        -------
        success : bool
            True/False based on whether the schedule was assigned without issue.
        """
        success = False

        if not self.__config.schedule_name:
            logger.error("Schedule name undefined!")
            return success

        assign_schedule_msg_tx_bin = Msg.AssignSchedule.Client.pack(
            {'channel': self.__config.channel, 'schedule': self.__config.schedule_name})
        response_msg_bin = self._send_receive_msg(
            assign_schedule_msg_tx_bin)

        if response_msg_bin:
            assign_schedule_msg_rx_dict = Msg.AssignSchedule.Server.unpack(
                response_msg_bin)
            if assign_schedule_msg_rx_dict['result'] == 'success':
                success = True
                logger.info(
                    f'Successfully assigned schedule {self.__config.schedule_name} to channel {self.__config.channel}')
                logger.info(assign_schedule_msg_rx_dict)
            else:
                logger.error(
                    f'Failed to assign schedule {self.__config.schedule_name}! Issue: {assign_schedule_msg_rx_dict["result"]}')
            self.__assign_schedule_feedback = assign_schedule_msg_rx_dict

        return success

    def start_test(self) -> bool:
        """
        Starts channel on method specified in config.  

        Returns
        -------
        success : bool
            True/False based on whether the test was started without issue.
        """
        success = False

        if not self.__config.test_name:
            logger.error("Test name undefined!")
            return success

        # Make sure the schedule is assigned before starting the test to avoid any funny business
        if self.assign_schedule():
            start_test_msg_tx_bin = Msg.StartSchedule.Client.pack(
                {'channel': self.__config.channel, 'test_name': self.__config.test_name})
            response_msg_bin = self._send_receive_msg(start_test_msg_tx_bin)

            if response_msg_bin:
                start_test_msg_rx_dict = Msg.StartSchedule.Server.unpack(
                    response_msg_bin)
                if start_test_msg_rx_dict['result'] == 'success':
                    success = True
                    logger.info(
                        f'Successfully started test {self.__config.test_name} with schedule {self.__config.schedule_name} on channel {self.__config.channel}')
                    logger.info(start_test_msg_rx_dict)
                else:
                    logger.error(
                        f'Failed to start test {self.__config.test_name} with schedule {self.__config.schedule_name} on channel {self.__config.channel}. Issue: {start_test_msg_rx_dict["result"]}')
                self.__start_test_feedback = start_test_msg_rx_dict

        return success

    def stop_test(self) -> bool:
        """
        Stops the test running on the channel specified in the config.

        Returns
        -------
        success : bool
            True/False based on whether the test stopped without issue.
            Also returns True if no test was running on the channel. 
        """
        success = False

        stop_test_msg_tx_bin = Msg.StopSchedule.Client.pack(
            {'channel': self.__config.channel})
        response_msg_bin = self._send_receive_msg(
            stop_test_msg_tx_bin)

        if response_msg_bin:
            stop_test_msg_rx_dict = Msg.StopSchedule.Server.unpack(
                response_msg_bin)
            if stop_test_msg_rx_dict['result'] == 'success':
                success = True
                logger.info(
                    f'Successfully stopped test on channel {self.__config.channel}')
                logger.info(stop_test_msg_rx_dict)
            else:
                logger.error(
                    f'Failed to stop test on channel {self.__config.channel}! Issue: {stop_test_msg_rx_dict["result"]}')
            self.__stop_test_feedback = stop_test_msg_rx_dict

        return success

    def set_meta_variable(self, mv_num: int, mv_value: float) -> bool:
        """
        Sets the passed meta variable number `mv_num` to the passed value `mv_value`
        on the channel specified in the config. Note the test must be running.

        Parameters
        ----------
        mv_num : int
            The meta variable number to set. Must be between 1 and 16 (inclusive)
        mv_value : float
            The meta variable value to set.
        Returns
        -------
        success : bool
            True/False based on whether the meta variable was set. 
        """
        success = False

        updated_msg_vals = {}
        updated_msg_vals['channel'] = self.__config.channel
        updated_msg_vals['mv_meta_code'] = Msg.SetMetaVariable.Client.mv_channel_codes[mv_num]
        updated_msg_vals['mv_data'] = mv_value

        set_mv_msg_tx_bin = Msg.SetMetaVariable.Client.pack(updated_msg_vals)
        response_msg_bin = self._send_receive_msg(
            set_mv_msg_tx_bin)

        if response_msg_bin:
            set_mv_msg_rx_dict = Msg.SetMetaVariable.Server.unpack(
                response_msg_bin)
            if set_mv_msg_rx_dict['result'] == 'success':
                success = True
                logger.info(
                    f'Successfully set meta variable {mv_num} to a value of {mv_value}')
                logger.info(set_mv_msg_rx_dict)
            else:
                logger.error(
                    f'Failed to set meta variable {mv_num} to a value of {mv_value}! Issue: {set_mv_msg_rx_dict["result"]}')
            self.set_mv_feedback = set_mv_msg_rx_dict

        return success

class ChannelInterfaceConfig(BaseModel):
    '''
    Holds channel config information for the CyclerInterface class.

    Parameters
    ----------
        channel : int
            The channel to target with the ChannelInterface class instance.
        test_name : *optional*
            The test name to use if using the ChannelInterface to start a test.
        schedule_name : str
            The name of the schedule file to use if using the ChannelInterface to start a test.
        ip_address : str 
            The IP address of the Maccor server. Use 127.0.0.1 if running on the same machine as the server.
        port : int 
            The port to communicate through with JSON messages. Default set to 57570.
        timeout_s : float 
            How long to wait before timing out on TCP communication. Defaults to 2 seconds. 
        msg_buffer_size : float 
             How big of a message buffer to use for sending/receiving messages. 
            A minimum of 1024 bytes is recommended. Defaults to 4096 bytes. 
    '''
    channel: int
    test_name: str = None
    schedule_name: str = None
    ip_address: str
    port: int
    timeout_s: float = 2.0
    msg_buffer_size: int = 4096

    @validator('channel')
    def username_alphanumeric(cls, v):
        if v < 1:
            raise ValueError('Channel must be greater than zero!')
        return v-1