"""
Modules for extracting time synchronization statistics for API 900 data.
Also includes functions for correcting time arrays.
ALL timestamps in microseconds unless otherwise stated
"""

# noinspection Mypy
import numpy as np
import pandas as pd

from typing import List, Optional
from redvox.common import stats_helper as sh, tri_message_stats as tms, date_time_utils as dt, file_statistics as fh
from redvox.common import sensor_data as sd


class TimeSyncData:
    """
    Stores latencies, offsets, and other timesync related information about a single station
    ALL timestamps in microseconds unless otherwise stated
    properties:
        station_id: str, id of station
        sample_rate_hz: float, sample rate of audio sensor in Hz
        mach_time_zero: int, timestamp of when the station was started
        packet_start_time: int, timestamp of when data started recording
        packet_end_time: int, timestamp of when data stopped recording
        server_acquisition_times: int, timestamp of when packet arrived at server
        time_sync_exchanges_df: dataframe, timestamps that form the time synch exchanges
        latencies: np.ndarray, calculated latencies of the exchanges
        best_latency_index: int, index in latencies array that contains the best latency
        best_latency: float, best latency of the data
        mean_latency: float, mean latency
        latency_std: float, standard deviation of latencies
        offsets: np.ndarray, calculated offsets of the exchanges
        best_offset: int, best offset of the data
        mean_offset: float, mean offset
        offset_std: float, standard deviation of offsets
        best_tri_msg_index: int, index of the best tri-message
        acquire_travel_time: int, calculated time it took packet to reach server
    """

    def __init__(self, data_pack: sd.DataPacket = None, station: sd.StationMetadata = None):
        """
        Initialize properties
        :param data_pack: data packet
        :param station: station metadata
        """
        self.best_latency: Optional[float] = None
        if station is None:
            self.station_id: Optional[str] = None
            self.station_start_timestamp: Optional[int] = None
        if data_pack is None:
            self.sample_rate_hz: Optional[float] = None
            self.server_acquisition_time: Optional[int] = None
            self.packet_start_time: Optional[int] = None
            self.packet_end_time: Optional[int] = None
            self.packet_duration: int = 0
            self.time_sync_exchanges_df = pd.DataFrame([], columns=["a1", "a2", "a3", "b1", "b2", "b3"])
            self.best_tri_msg_index: Optional[int] = None
            self.latencies: np.ndarray = np.ndarray((0, 0))
            self.best_latency_index: Optional[int] = None
            self.mean_latency: Optional[float] = None
            self.latency_std: Optional[float] = None
            self.offsets: np.ndarray = np.ndarray((0, 0))
            self.best_offset: int = 0
            self.mean_offset: Optional[float] = 0.0
            self.offset_std: Optional[float] = 0.0
            self.acquire_travel_time: Optional[int] = None
            # self.num_packets: int = 0
            # self.bad_packets: List[int] = []
        else:
            self.get_timesync_data(data_pack, station)

    def get_timesync_data(self, data_pack: sd.DataPacket, station: sd.StationMetadata):
        """
        extracts the time sync data from the data_pack object
        :param data_pack: data packet to get data from
        :param station: station metadata
        """
        self.station_id = station.station_id
        self.sample_rate_hz = station.timing_data.audio_sample_rate_hz
        self.station_start_timestamp = station.timing_data.station_start_timestamp
        self.server_acquisition_time = data_pack.server_timestamp
        self.packet_start_time = data_pack.packet_start_timestamp
        self.packet_end_time = data_pack.packet_end_timestamp
        if data_pack.timesync is not None:
            self.time_sync_exchanges_df = pd.DataFrame(
                tms.transmit_receive_timestamps_microsec(data_pack.timesync),
                index=["a1", "a2", "a3", "b1", "b2", "b3"]).T
        else:
            self.time_sync_exchanges_df = pd.DataFrame([], columns=["a1", "a2", "a3", "b1", "b2", "b3"])
        # stations may contain the best latency and offset data already
        if data_pack.packet_best_latency:
            self.best_latency = data_pack.packet_best_latency
        if data_pack.packet_best_offset:
            self.best_offset = data_pack.packet_best_offset
        self._compute_tri_message_stats()
        # set the packet duration (this should also be equal to self.packet_end_time - self.packet_start_time)
        self.packet_duration = dt.seconds_to_microseconds(
            fh.get_duration_seconds_from_sample_rate(int(self.sample_rate_hz)))
        # calculate travel time between corrected end of packet timestamp and server timestamp
        self.acquire_travel_time = self.server_acquisition_time - (self.packet_end_time + self.best_offset)

    def _compute_tri_message_stats(self):
        """
        Compute the tri-message stats from the data
        """
        if self.num_tri_messages() > 0:
            # compute tri message data from time sync exchanges
            tse = tms.TriMessageStats(self.station_id,
                                      self.time_sync_exchanges_df["a1"], self.time_sync_exchanges_df["a2"],
                                      self.time_sync_exchanges_df["a3"],
                                      self.time_sync_exchanges_df["b1"], self.time_sync_exchanges_df["b2"],
                                      self.time_sync_exchanges_df["b3"])
            # Compute the statistics for latency and offset
            self.mean_latency = np.mean([*tse.latency1, *tse.latency3])
            self.latency_std = np.std([*tse.latency1, *tse.latency3])
            self.mean_offset = np.mean([*tse.offset1, *tse.offset3])
            self.offset_std = np.std([*tse.offset1, *tse.offset3])
            self.latencies = np.array((tse.latency1, tse.latency3))
            self.offsets = np.array((tse.offset1, tse.offset3))
            self.best_latency_index = tse.best_latency_index
            self.best_tri_msg_index = tse.best_latency_index
            # if best_latency is None, set to best computed latency
            if self.best_latency is None:
                self.best_latency = tse.best_latency
                self.best_offset = tse.best_offset
            # if best_offset is still default value, use the best computed offset
            elif self.best_offset == 0:
                self.best_offset = tse.best_offset
        else:
            # If here, there are no exchanges to read.  writing default or empty values to the correct properties
            self.best_tri_msg_index = None
            self.best_latency_index = None
            self.best_latency = None
            self.mean_latency = np.nan
            self.latency_std = np.nan
            self.best_offset = 0
            self.mean_offset = 0
            self.offset_std = 0

    def num_tri_messages(self) -> int:
        return self.time_sync_exchanges_df.shape[0]


class TimeSyncAnalysis:
    """
    Used for multiple TimeSyncData objects from a station
    properties:
        station: the station that contains the data to analyze
    """
    def __init__(self, station: sd.Station = None):
        self.station_id: str = ""
        self.best_latency_index: int = 0
        self.latency_stats = sh.StatsContainer("latency")
        self.offset_stats = sh.StatsContainer("offset")
        self.station_start_timestamp: Optional[int] = None
        self.sample_rate_hz: float = 0
        self.timesync_data: List[TimeSyncData] = []
        if station is not None:
            self.station_id: str = station.station_metadata.station_id
            self.station_start_timestamp: int = station.station_metadata.timing_data.station_start_timestamp
            self.sample_rate_hz: float = station.station_metadata.timing_data.audio_sample_rate_hz
            self.timesync_data: List[TimeSyncData] = get_time_sync_data(station)
            self.evaluate_and_validate_data()

    def evaluate_and_validate_data(self):
        self._calc_timesync_stats()
        self.evaluate_latencies()
        if self.validate_start_timestamp():
            self.station_start_timestamp = self.timesync_data[0].station_start_timestamp
        if self.validate_sample_rate():
            self.sample_rate_hz = self.timesync_data[0].sample_rate_hz

    def _calc_timesync_stats(self):
        """
        calculates the mean and std deviation for latencies and offsets
        """
        if len(self.timesync_data) < 1:
            raise ValueError("Nothing to calculate stats; length of timesync data is less than 1")
        # reset the stats containers
        self.latency_stats = sh.StatsContainer("latency")
        self.offset_stats = sh.StatsContainer("offset")
        for index in range(len(self.timesync_data)):
            # add the stats of the latency
            self.latency_stats.add(self.timesync_data[index].mean_latency, self.timesync_data[index].latency_std,
                                   self.timesync_data[index].num_tri_messages() * 2)
            # add the stats of the offset
            self.offset_stats.add(self.timesync_data[index].mean_offset, self.timesync_data[index].offset_std,
                                  self.timesync_data[index].num_tri_messages() * 2)

    def add_timesync_data(self, timesync_data: TimeSyncData):
        self.timesync_data.append(timesync_data)
        self.evaluate_and_validate_data()

    def get_num_packets(self) -> int:
        return len(self.timesync_data)

    def get_best_latency(self) -> float:
        return self.timesync_data[self.best_latency_index].best_latency

    def get_latencies(self) -> np.array:
        latencies = []
        for ts_data in self.timesync_data:
            latencies.append(ts_data.best_latency)
        return np.array(latencies)

    def get_mean_latency(self):
        mean = self.latency_stats.mean_of_means()
        if np.isnan(mean):
            return None
        return mean

    def get_latency_std(self):
        std_dev = self.latency_stats.total_std_dev()
        if np.isnan(std_dev):
            return None
        return std_dev

    def get_best_offset(self):
        return self.timesync_data[self.best_latency_index].best_offset

    def get_offsets(self) -> np.array:
        offsets = []
        for ts_data in self.timesync_data:
            offsets.append(ts_data.best_offset)
        return np.array(offsets)

    def get_mean_offset(self):
        mean = self.offset_stats.mean_of_means()
        if np.isnan(mean):
            return None
        return mean

    def get_offset_std(self):
        std_dev = self.offset_stats.total_std_dev()
        if np.isnan(std_dev):
            return None
        return std_dev

    def get_best_packet_latency_index(self):
        return self.timesync_data[self.best_latency_index].best_latency_index

    def get_best_start_time(self):
        return self.timesync_data[self.best_latency_index].packet_start_time

    def get_start_times(self) -> np.array:
        start_times = []
        for ts_data in self.timesync_data:
            start_times.append(ts_data.packet_start_time)
        return np.array(start_times)

    def get_bad_packets(self) -> List[int]:
        bad_packets = []
        for idx in range(self.get_num_packets()):  # mark bad indices (they have a 0 or less value)
            if self.get_latencies()[idx] <= 0 or np.isnan(self.get_latencies()[idx]):
                bad_packets.append(idx)
        return bad_packets

    def evaluate_latencies(self):
        """
        finds the best latency
        outputs warnings if a change in timestamps is detected
        """
        if self.get_num_packets() < 1:
            raise ValueError("Nothing to evaluate; length of timesync data is less than 1")
        # assume the first element has the best timesync values for now, then compare with the others
        for index in range(1, self.get_num_packets()):
            # find the best latency; in this case, the minimum
            # if new value is not None and if the current best is None or new value is better than current best, update
            if self.timesync_data[index].best_latency is not None \
                    and (self.get_best_latency() is None
                         or self.timesync_data[index].best_latency < self.get_best_latency()):
                self.best_latency_index = index

    def validate_start_timestamp(self) -> bool:
        """
        confirms if station_start_timestamp differs in any of the timesync_data
        outputs warnings if a change in timestamps is detected
        :return: True if no change
        """
        if self.get_num_packets() < 1:
            raise ValueError("Nothing to evaluate; length of timesync data is less than 1")
        for index in range(1, self.get_num_packets()):
            # compare station start timestamps; notify when they are different
            if self.timesync_data[index].station_start_timestamp != self.station_start_timestamp:
                print(f"Warning!  Change in station start timestamp detected!  "
                      f"Expected: {self.station_start_timestamp}, read: "
                      f"{self.timesync_data[index].station_start_timestamp}")
                return False
        # if here, all the sample timestamps are the same
        return True

    def validate_sample_rate(self) -> bool:
        """
        confirms if sample rate is the same across all timesync_data
        outputs warning if a change in sample rate is detected
        :return: True if no change
        """
        if self.get_num_packets() < 1:
            raise ValueError("Nothing to evaluate; length of timesync data is less than 1")
        for index in range(1, self.get_num_packets()):
            # compare station start timestamps; notify when they are different
            if self.timesync_data[index].sample_rate_hz is None \
                    or self.timesync_data[index].sample_rate_hz != self.sample_rate_hz:
                print(f"Warning!  Change in station sample rate detected!  "
                      f"Expected: {self.sample_rate_hz}, read: {self.timesync_data[index].sample_rate_hz}")
                return False
        # if here, all the sample rates are the same
        return True


def get_time_sync_data(station: sd.Station) -> List[TimeSyncData]:
    timesync_list = []
    for packet in station.sensor_list:
        timesync_list.append(TimeSyncData(packet, station.station_metadata))
    return timesync_list


def validate_sensors(tsa_data: TimeSyncAnalysis) -> bool:
    """
    Examine all sample rates and mach time zeros to ensure that sensor settings do not change
    :param tsa_data: the TimeSyncAnalysis data to validate
    :return: True if sensor settings do not change
    """
    # check that we have packets to read
    if tsa_data.get_num_packets() < 1:
        print("ERROR: no data to validate.")
        return False
    elif tsa_data.get_num_packets() > 1:
        # if we have more than one packet, we need to validate the data
        return tsa_data.validate_sample_rate() and tsa_data.validate_start_timestamp()
    # we get here if all packets have the same sample rate and mach time zero
    return True


def update_evenly_sampled_time_array(ts_analysis: TimeSyncAnalysis, num_samples: float = None,
                                     time_start_array: np.array = None) -> np.ndarray:
    """
    Correct evenly sampled times using updated time_start_array values as the focal point.
    Expects tsd to have the same number of packets as elements in time_start_array
    Inserts data gaps where necessary before building array.
    Throws an exception if the number of packets in tsa does not match the length of time_start_array

    :param ts_analysis: TimeSyncAnalysis object that contains the information needed to update the time array
    :param num_samples: number of samples in one file; optional, uses number based on sample rate if not given
    :param time_start_array: the list of timestamps to correct in seconds; optional, uses the start times in the
                             TimeSyncAnalysis object if not given
    :return: Revised time array in epoch seconds
    """
    if not validate_sensors(ts_analysis):
        raise AttributeError("ERROR: Change in Station Start Time or Sample Rate detected!")
    if time_start_array is None:
        # replace the time_start_array with values from tsd; convert tsd times to seconds
        time_start_array: List[float] = []
        for tsd in ts_analysis.timesync_data:
            time_start_array.append(tsd.packet_start_time / dt.MICROSECONDS_IN_SECOND)
    num_files = len(ts_analysis.timesync_data)
    # the TimeSyncData must have the same number of packets as the number of elements in time_start_array
    if num_files != len(time_start_array):
        # alert the user, then quit
        raise Exception("ERROR: Attempted to update a time array that doesn't contain "
                        "the same number of elements as the TimeSyncAnalysis!")

    if num_samples is None:
        num_samples = fh.get_num_points_from_sample_rate(ts_analysis.sample_rate_hz)
    t_dt = 1.0 / ts_analysis.sample_rate_hz

    # Use TimeSyncData object to find best start index.
    # Samples before will be the number of decoders before a0 times the number of samples in a file.
    # Samples after will be the number of decoders after a0 times the number of samples in a file minus 1;
    # the minus one represents the best a0.
    decoder_idx = ts_analysis.best_latency_index
    samples_before = int(decoder_idx * num_samples)
    samples_after = round((num_files - decoder_idx) * num_samples) - 1
    best_start_sec = time_start_array[decoder_idx]

    # build the time arrays separately in epoch seconds, then join into one
    # add 1 to include the actual a0 sample, then add 1 again to skip the a0 sample; this avoids repetition
    timesec_before = np.vectorize(lambda t: best_start_sec - t * t_dt)(list(range(int(samples_before + 1))))
    timesec_before = timesec_before[::-1]  # reverse 'before' times so they increase from earliest start time
    timesec_after = np.vectorize(lambda t: best_start_sec + t * t_dt)(list(range(1, int(samples_after + 1))))
    timesec_rev = np.concatenate([timesec_before, timesec_after])

    return timesec_rev


def update_time_array(ts_data: TimeSyncData, time_array: np.array) -> np.ndarray:
    """
    Correct timestamps in time_array using information from TimeSyncData
    :param ts_data: TimeSyncData object that contains the information needed to update the time array
    :param time_array: the list of timestamps to correct in seconds
    :return: Revised time array in epoch seconds
    """
    return time_array + (ts_data.best_offset / dt.MICROSECONDS_IN_SECOND)


def update_time_array_from_analysis(ts_analysis: TimeSyncAnalysis, time_array: np.array) -> np.ndarray:
    """
    Correct timestamps in time_array using information from TimeSyncAnalysis
    :param ts_analysis: TimeSyncAnalysis object that contains the information needed to update the time array
    :param time_array: the list of timestamps to correct in seconds
    :return: Revised time array in epoch seconds
    """
    return time_array + (ts_analysis.get_best_offset() / dt.MICROSECONDS_IN_SECOND)
