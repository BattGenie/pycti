import socket
import threading
import struct
import copy
from pyctiarbin.messages import Msg, MessageABC


class ChannelData:

    __chan_readings_list = []
    __chan_readings_lock = threading.Lock()

    def __init__(self, num_channels):
        """
        Container class that will hold all of the specific channel data for ArbinSpoofer.

        Parameters
        ----------
            num_channels : int
                Number of channels in our hypothetical Arbin cycler.
        """
        self.num_channels = num_channels

        # Create channel_readings for all of the channels.
        for i in range(0, self.num_channels):
            channel_readings = {}
            for key, item in Msg.ChannelInfo.Server.msg_specific_template.items():
                channel_readings[key] = copy.deepcopy(item['value'])
            channel_readings['channel'] = i
            with self.__chan_readings_lock:
                self.__chan_readings_list.append(
                    copy.deepcopy(channel_readings))

    def fetch_channel_readings(self, channel) -> dict:
        """
        Returns the status message for a specified channel.

        Parameters
        ----------
        channel : int
            The channel to return the status for.

        Returns
        -------
        status : dict
            The status message for the requested channel. Empty if channel larger than number of channel
        """
        if channel > self.num_channels:
            return {}
        else:
            with self.__chan_readings_lock:
                return copy.deepcopy(self.__chan_readings_list[channel])

    def update_channel_readings(self, channel, updated_readings):
        """
        Updates the stored channel readings for the specified channel.

        Parameters
        ----------
        channel : int
            The channel to update the readings for.
        updated_status : dict
            Complete or partial dictionary of status values to update.

        Returns
        -------
        success : bool
            Returns True if all values in the updated_status were used to update the channel_status_array.
        """
        if channel > self.num_channels:
            return False
        else:
            for key in updated_readings.keys():
                if key not in Msg.ChannelInfo.Server.msg_specific_template.keys():
                    return False

            with self.__chan_readings_lock:
                for key in updated_readings.keys():
                    self.__chan_readings_list[channel][key] = updated_readings[key]


class SocketWorker:
    """
    Generic worker class that will respond to client socket requests.
    Default setup as an echo server. Child classes should overwrite the
    the `_process_client_msg()` method with their own responses.
    """
    __receive_msg_timeout_s = 0.5
    __msg_buffer_size_bytes = 2**12
    __stop_lock = threading.Lock()
    __stop = False

    def __init__(self, s: socket.socket, channel_data: ChannelData):
        """
        Creates the thread to service client requests.

        Parameters
        ----------
        s : socket.socket
            Socket connection to client.
        """
        self.__channel_data = channel_data

        self.stop = False
        self.__client_thread = threading.Thread(
            target=self.__service_loop,
            args=(s,),
            daemon=True
        )
        self.__client_thread.start()

    def __service_loop(self, s: socket.socket):
        """
        Forever loop to service client requests. Wait to receive a message. If no messages is
        received before the timeout then check to see if stop command has been issued. Loop is
        also broken if client breaks connection by sending b''.

        Parameters
        ----------
        s : socket.socket
            Socket connection to client.
        """
        s.settimeout(self.__receive_msg_timeout_s)

        rx_msg_length_format = MessageABC.base_template['msg_length']['format']
        rx_msg_length_start_byte = MessageABC.base_template['msg_length']['start_byte']
        rx_msg_length_end_byte = MessageABC.base_template['msg_length']['start_byte'] + struct.calcsize(
            rx_msg_length_format)

        while True:
            try:
                rx_msg = s.recv(self.__msg_buffer_size_bytes)
                if not rx_msg:
                    break

                # Keep reading message in pieces until rx_msg is as long as expected_rx_msg_len
                expected_rx_msg_len = struct.unpack(
                    rx_msg_length_format, rx_msg[rx_msg_length_start_byte:rx_msg_length_end_byte])[0]
                while len(rx_msg) < expected_rx_msg_len:
                    rx_msg += s.recv(self.__msg_buffer_size_bytes)

                tx_msg = self.__process_client_msg(rx_msg)

                s.sendall(tx_msg)
            except socket.timeout:
                with self.__stop_lock:
                    if self.__stop:
                        break
        s.close()

    def __process_client_msg(self, rx_msg):
        """
        Takes the incoming client message and generates a response.

        Parameters
        ----------
        rx_msg : bytearray
            The client message received.

        Returns
        -------
        tx_msg : PyBytesObject
            The client response.
        """

        # Determine command code to sort message
        cmd_code_format = MessageABC.base_template['command_code']['format']
        cmd_code_start_byte = MessageABC.base_template['command_code']['start_byte']
        cmd_code_end_byte = MessageABC.base_template['command_code']['start_byte'] + + struct.calcsize(
            cmd_code_format)
        cmd_code = struct.unpack(
            cmd_code_format, rx_msg[cmd_code_start_byte:cmd_code_end_byte])[0]

        if cmd_code == Msg.Login.Client.command_code:
            rx_msg_dict = Msg.Login.Client.unpack(rx_msg)
            tx_msg = Msg.Login.Server.pack(
                {'num_channels': self.__channel_data.num_channels})
        elif cmd_code == Msg.ChannelInfo.Client.command_code:
            rx_msg_dict = Msg.ChannelInfo.Client.unpack(rx_msg)
            channel_values = self.__channel_data.fetch_channel_readings(
                rx_msg_dict['channel'])
            tx_msg = Msg.ChannelInfo.Server.pack(channel_values)
        elif cmd_code == Msg.AssignSchedule.Client.command_code:
            rx_msg_dict = Msg.AssignSchedule.Client.unpack(rx_msg)
            tx_msg = Msg.AssignSchedule.Server.pack(
                {'channel': rx_msg_dict['channel']})
        elif cmd_code == Msg.StartSchedule.Client.command_code:
            rx_msg_dict = Msg.StartSchedule.Client.unpack(rx_msg)
            tx_msg = Msg.StartSchedule.Server.pack(
                {'channel': rx_msg_dict['channel']})
        elif cmd_code == Msg.StopSchedule.Client.command_code:
            rx_msg_dict = Msg.StopSchedule.Client.unpack(rx_msg)
            tx_msg = Msg.StopSchedule.Server.pack(
                {'channel': rx_msg_dict['channel']})
        elif cmd_code == Msg.JumpChannel.Client.command_code:
            rx_msg_dict = Msg.JumpChannel.Client.unpack(rx_msg)
            tx_msg = Msg.JumpChannel.Server.pack(
                {'channel': rx_msg_dict['channel']})
        elif cmd_code == Msg.SetMetaVariable.Client.command_code:
            rx_msg_dict = Msg.SetMetaVariable.Client.unpack(rx_msg)
            tx_msg = Msg.SetMetaVariable.Server.pack(
                {'channel': rx_msg_dict['channel']})
        else:
            tx_msg = bytearray([])

        return tx_msg

    def is_alive(self):
        """
        Method to call to see if the client service thread is still running.

        Returns
        -------
        running : bool
            True of False based on whether or not the client thread is running.
        """
        return self.__client_thread.is_alive()

    def kill_worker(self):
        """
        Method to stop client service loop.
        """
        if self.__client_thread.is_alive():
            with self.__stop_lock:
                self.__stop = True
            self.__client_thread.join()


class ArbinSpoofer:

    __client_connect_timeout_s = 0.5
    __stop_servers_lock = threading.Lock()
    __stop_servers = False

    def __init__(self, config: dict):
        """
        Class to mimic behavior of Arbin cycler MITSPro control server. The class is currently dumb
        and just sends back basic channel messages without any notion of channel status.
        It could be expanded in future.

        Parameters
        ----------
        config : dict
            A configuration dictionary containing the following fields:

            `ip`: The server IP address to host from. Most often will be 'localhost' for testing.

            `port`: The port to use for the server.

            `num_channels`: The number of channel our fictitious cycler has.
        """
        self.__channel_data = ChannelData(config['num_channels'])

        self.__server_thread = threading.Thread(
            target=self.__server_loop,
            args=(config, SocketWorker,),
            daemon=True
        )

    def start(self):
        """
        Starts the server loops.
        """
        self.__server_thread.start()

    def update_channel_status(self, channel, updated_readings):
        """
        Updates the stored channel status for the specified channel.

        Parameters
        ----------
        channel : int
            The channel to update the status for.
        updated_readings : dict
            Complete or partial dictionary of status values to update.

        Returns
        -------
        success : bool
            Returns True if all values in the updated_status were used to update the channel_status_array.
        """
        return self.__channel_data.update_channel_readings(channel, updated_readings)

    def __server_loop(self, sock_config: dict, Worker: SocketWorker):
        """
        Creates a server and forever loop to service client socket requests.

        Parameters
        ----------
        sock_config : dict
            A configuration for the socket containing the IP and port number.
        Worker : SocketWorker
            A reference to the worker class that will service individual client connections.
        """
        # List that will hold all the workers to service client connections.
        client_workers = []

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((sock_config["ip"], sock_config["port"]))
        sock.settimeout(self.__client_connect_timeout_s)
        sock.listen()

        while True:
            try:
                client_connection = sock.accept()[0]
                client_workers.append(
                    Worker(client_connection, self.__channel_data))
            except socket.timeout:
                with self.__stop_servers_lock:
                    # If stop command is issued then kill all workers.
                    if self.__stop_servers:
                        for worker in client_workers:
                            if worker.is_alive():
                                worker.kill_worker()
                        break
                # Remove any workers that made have died from disconnecting clients.
                client_workers[:] = [
                    worker for worker in client_workers if worker.is_alive()
                ]

        sock.close()

    def stop(self):
        """
        Stop the server loops.
        """
        with self.__stop_servers_lock:
            self.__stop_servers = True
        self.__server_thread.join()

    def __del__(self):
        self.stop()
