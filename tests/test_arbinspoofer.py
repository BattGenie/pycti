import pytest
from helper_test_utils import Constants, TcpClient
from pyctiarbin.arbinspoofer import ArbinSpoofer
from pyctiarbin.messages import Msg

"""
Various parameters we will use across all the tests.
"""
CONFIG_DICT = {"ip": "127.0.0.1",
               "port": 5678,
               "num_channels": 16}
CHANNEL = 5  # The channel we will use to associated tests messages.


@pytest.mark.arbinspoofer
def test_messages():
    """
    Test that the spoofer replies correctly to all messages.
    """
    CONFIG_DICT['port'] = 5678
    arbin_spoofer = ArbinSpoofer(CONFIG_DICT)
    arbin_spoofer.start()

    client = TcpClient(CONFIG_DICT)

    # Send all messages and make sure we get the correct responses.
    messages = [(Msg.Login.Client.pack(),
                 Msg.Login.Server.pack({'num_channels': CONFIG_DICT['num_channels']})),
                (Msg.ChannelInfo.Client.pack(),
                    Msg.ChannelInfo.Server.pack()),
                (Msg.AssignSchedule.Client.pack(),
                    Msg.AssignSchedule.Server.pack()),
                (Msg.StartSchedule.Client.pack(),
                    Msg.StartSchedule.Server.pack()),
                (Msg.StopSchedule.Client.pack(),
                    Msg.StopSchedule.Server.pack()),
                (Msg.JumpChannel.Client.pack(),
                    Msg.JumpChannel.Server.pack()),
                (Msg.SetMetaVariable.Client.pack(),
                    Msg.SetMetaVariable.Server.pack()),
                ]

    for tx_msg, expected_rx_msg in messages:
        rx_msg = client.send_recv_msg(tx_msg)
        assert (rx_msg == expected_rx_msg)

    arbin_spoofer.stop()


@pytest.mark.arbinspoofer
def test_update_status():
    """
    Check that updating channel status info works.
    """
    CONFIG_DICT['port'] = 5679
    arbin_spoofer = ArbinSpoofer(CONFIG_DICT)
    arbin_spoofer.start()

    client = TcpClient(CONFIG_DICT)

    # Check initial channel readings
    tx_msg = Msg.ChannelInfo.Client.pack({'channel': CHANNEL})
    rx_msg = client.send_recv_msg(tx_msg)
    # Generate the message we would expect to get back
    rx_msg_expected = Msg.ChannelInfo.Server.pack({'channel': CHANNEL})
    assert (rx_msg == rx_msg_expected)

    # Now check updating the values
    updated_readings = {'voltage_v': 2.69, 'current_a': 1.19}
    arbin_spoofer.update_channel_status(CHANNEL, updated_readings)
    rx_msg = client.send_recv_msg(tx_msg)
    # Generate the message we would expect to get back with updated values
    rx_msg_expected = Msg.ChannelInfo.Server.pack(
        {**{'channel': CHANNEL}, **updated_readings})
    # Check it in binary
    assert (rx_msg == rx_msg_expected)

    # Now check it unpacked
    rx_msg_dict = Msg.ChannelInfo.Server.unpack(rx_msg)
    assert (abs(updated_readings['voltage_v'] - rx_msg_dict['voltage_v'])
            < Constants.FLOAT_TOLERANCE)
    assert (abs(updated_readings['current_a'] - rx_msg_dict['current_a'])
            < Constants.FLOAT_TOLERANCE)

    arbin_spoofer.stop()
