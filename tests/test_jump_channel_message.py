import pytest
import os
import copy
from pyctiarbin import Msg
from helper_test_utils import message_file_loader

MSG_DIR = os.path.join(os.path.dirname(__file__), 'example_messages')


@pytest.mark.messages
def test_jump_channel_client_message():
    '''
    Test packing/parsing a client jump channel request message
    '''

    example_msg_name = 'client_jump_channel_msg'
    (msg_bin, msg_dict) = message_file_loader(MSG_DIR, example_msg_name)

    # Pack the msg_dict and check if it matches the example binary message
    packed_msg = Msg.JumpChannel.Client.pack(msg_dict)
    assert (packed_msg == msg_bin)

    # Checking parsing the example message binary and that it matches the msg_dict
    parsed_msg = Msg.JumpChannel.Client.unpack(msg_bin)
    assert (parsed_msg == msg_dict)


@pytest.mark.messages
def test_jump_channel_server_message():
    '''
    Test parsing/packing a server jump channel response message
    '''
    example_msg_name = 'server_jump_channel_msg'
    (msg_bin, msg_dict) = message_file_loader(MSG_DIR, example_msg_name)

    # Check that the parsed binary message matches the msg_dict
    parsed_msg = Msg.JumpChannel.Server.unpack(msg_bin)
    assert (parsed_msg == msg_dict)

    # Check packing own version of message from msg_dict
    buildable_msg_dict = copy.deepcopy(msg_dict)
    # Need to re-code this from login_result_decoder
    buildable_msg_dict['result'] = '\0'
    packed_msg = Msg.JumpChannel.Server.pack(buildable_msg_dict)
    parsed_msg = Msg.JumpChannel.Server.unpack(packed_msg)
    assert (parsed_msg == msg_dict)
