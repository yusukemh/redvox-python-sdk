import unittest
import numpy as np
import redvox.api1000.wrapped_redvox_packet.common as common
import redvox.api1000.wrapped_redvox_packet.sensors.audio as microphone


class TestAudio(unittest.TestCase):
    def setUp(self) -> None:
        self.empty_microphone_sensor: microphone.Audio = microphone.Audio.new()
        self.non_empty_microphone_sensor: microphone.Audio = microphone.Audio.new()
        self.non_empty_microphone_sensor.get_samples().set_unit(common.Unit['DECIBEL'])
        self.non_empty_microphone_sensor.get_samples().set_values(np.array([100.0, 50, 10.25], dtype=np.int))
        self.non_empty_microphone_sensor.set_sensor_description("foo")
        self.non_empty_microphone_sensor.set_sample_rate(80.0)
        self.non_empty_microphone_sensor.set_first_sample_timestamp(1)
        self.non_empty_microphone_sensor.get_metadata().set_metadata({"foo": "bar"})

    def test_validate_audio(self):
        error_list = microphone.validate_audio(self.non_empty_microphone_sensor)
        self.assertEqual(error_list, [])
        error_list = microphone.validate_audio(self.empty_microphone_sensor)
        self.assertNotEqual(error_list, [])
