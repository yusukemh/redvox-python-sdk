"""
This module creates specific time-bounded segments of data for users
"""
import pandas as pd
import numpy as np
from typing import Optional, Set
from dataclasses import dataclass

from redvox.common import date_time_utils as dtu

from redvox.common.sensor_data import SensorType
from redvox.common.load_sensor_data import ReadResult, read_all_in_dir
from redvox.api1000.wrapped_redvox_packet.sensors.location import LocationProvider


DEFAULT_GAP_TIME_S: float = 0.25
DEFAULT_START_PADDING_S: float = 120.
DEFAULT_END_PADDING_S: float = 120.


@dataclass
class DataWindow:
    """
    Holds the data for a given time window; adds interpolated timestamps to fill gaps and pad start and end values
    Properties:
        input_directory: string, directory that contains the files to read data from.  REQUIRED
        station_ids: optional set of strings, list of station ids to filter on.
                        If empty or None, get any ids found in the input directory.  Default None
        start_datetime: optional datetime, start datetime of the window.
                        If None, uses the first timestamp of the filtered data.  Default None
        end_datetime: optional datetime, end datetime of the window.
                        If None, uses the last timestamp of the filtered data.  Default None
        start_padding_s: float, the amount of seconds to include before the start_datetime
                            when filtering data.  Default DEFAULT_START_PADDING_S
        end_padding_s: float, the amount of seconds to include after the end_datetime
                        when filtering data.  Default DEFAULT_END_PADDING_S
        gap_time_s: float, the minimum amount of seconds between data points that would indicate a gap.
                    Default DEFAULT_GAP_TIME_S
        apply_correction: bool, if True, update the timestamps in the data based on best station offset.  Default True
        structured_layout: bool, if True, the input_directory contains specially named and organized
                            directories of data.  Default True
        stations: optional ReadResult, the results of reading the data from input_directory
    """
    input_directory: str
    station_ids: Optional[Set[str]] = None
    start_datetime: Optional[dtu.datetime] = None
    end_datetime: Optional[dtu.datetime] = None
    start_padding_s: float = DEFAULT_START_PADDING_S
    end_padding_s: float = DEFAULT_END_PADDING_S
    gap_time_s: float = DEFAULT_GAP_TIME_S
    apply_correction: bool = True
    structured_layout: bool = True
    stations: Optional[ReadResult] = None

    def __post_init__(self):
        """
        loads the data after initialization
        """
        if self.stations is None:
            self.read_data()

    def copy(self) -> 'DataWindow':
        """
        :return: a copy of the DataWindow
        """
        return DataWindow(self.input_directory, self.station_ids, self.start_datetime, self.end_datetime,
                          self.start_padding_s, self.end_padding_s, self.gap_time_s,
                          self.apply_correction, self.structured_layout, self.stations)

    def _has_time_window(self) -> bool:
        """
        Returns true if there is a start or end datetime in the settings
        :return: True if start_datetime or end_datetime exists
        """
        return self.start_datetime is not None or self.end_datetime is not None

    def _pad_start_datetime_s(self) -> float:
        """
        apply padding to the start datetime
        :return: padded start datetime as seconds since epoch UTC
        """
        return dtu.datetime_to_epoch_seconds_utc(self.start_datetime) - self.start_padding_s

    def _pad_end_datetime_s(self) -> float:
        """
        apply padding to the end datetime
        :return: padded end datetime as seconds since epoch UTC
        """
        return dtu.datetime_to_epoch_seconds_utc(self.end_datetime) + self.end_padding_s

    def correct_timestamps(self):
        """
        update the timestamps in all stations
        """
        for station in self.stations.station_id_uuid_to_stations.values():
            if self.apply_correction:
                station.update_timestamps()

    def read_data(self):
        """
        read data using the properties of the class
        """
        start_time = int(self._pad_start_datetime_s()) if self.start_datetime else None
        end_time = int(self._pad_end_datetime_s()) if self.end_datetime else None
        self.stations = read_all_in_dir(self.input_directory, start_time, end_time,
                                        self.station_ids, self.structured_layout)

        ids_to_pop = []
        # check if ids in station data from files
        for ids in self.station_ids:
            if not self.stations.check_for_id(ids):
                # error handling
                print(f"WARNING: {ids} doesn't have any data to read")
        for station in self.stations.get_all_stations():
            station_id = station.station_metadata.station_id
            if not station.has_audio_data():
                # if no audio data, its like the station doesn't exist
                print(f"WARNING: {station_id} doesn't have any audio data to read")
                ids_to_pop.append(station_id)
                break  # stop processing and move on to next station
            # apply time correction
            if self.apply_correction:
                station.update_timestamps()
            station.packet_gap_detector(self.gap_time_s)
            # set the window start and end if they were specified, otherwise use the bounds of the data
            start_datetime = dtu.datetime_to_epoch_microseconds_utc(self.start_datetime) \
                if self.start_datetime else float(station.audio_sensor().first_data_timestamp())
            end_datetime = dtu.datetime_to_epoch_microseconds_utc(self.end_datetime) \
                if self.end_datetime else float(station.audio_sensor().last_data_timestamp())
            # location processing
            if station.has_location_data():
                # anything with 0 altitude is likely a network provided location
                station.location_sensor().data_df.loc[(station.location_sensor().data_df["altitude"] == 0),
                                                      "location_provider"] = LocationProvider.NETWORK
            station.update_station_location_metadata(start_datetime, end_datetime)
            # TRUNCATE!
            # truncate packets to include only the ones with the data for the window
            station.packet_data = [p for p in station.packet_data
                                   if p.data_end_timestamp > start_datetime and
                                   p.data_start_timestamp < end_datetime]
            for sensor_type, sensor in station.station_data.items():
                # get only the timestamps between the start and end timestamps
                df_timestamps = sensor.data_timestamps()
                if len(df_timestamps) < 1:
                    print(f"WARNING: Data window for {station_id} {sensor_type.name} sensor has no data points!")
                    break
                window_indices = np.where((start_datetime <= df_timestamps) & (df_timestamps <= end_datetime))[0]
                # oops, all the samples have been cut off
                if len(window_indices) < 1:
                    print(f"WARNING: Data window for {station_id} {sensor_type.name} "
                          f"sensor has truncated all data points")
                    if sensor_type == SensorType.AUDIO:
                        ids_to_pop.append(station_id)
                else:
                    sensor.data_df = sensor.data_df.iloc[window_indices].reset_index(drop=True)
                    if sensor.is_sample_interval_invalid():
                        print(f"WARNING: {station_id} {sensor_type.name} "
                              f"sensor has undefined sample interval and sample rate!")
                    else:
                        # GAP FILL
                        sensor.data_df = gap_filler(sensor.data_df, sensor.sample_interval_s)
                        # PAD DATA
                        sensor.data_df = data_padder(start_datetime, end_datetime,
                                                     sensor.data_df, sensor.sample_interval_s)
            # reassign the station's metadata to match up with updated sensor data
            station.station_metadata.timing_data.station_first_data_timestamp = \
                station.audio_sensor().first_data_timestamp()
            station.station_metadata.timing_data.episode_start_timestamp_s = start_datetime
            station.station_metadata.timing_data.episode_end_timestamp_s = end_datetime
        # remove any stations that don't have audio data
        for ids in ids_to_pop:
            self.stations.pop_station(ids)


def data_padder(expected_start: float, expected_end: float, data_df: pd.DataFrame,
                sample_interval_s: float) -> pd.DataFrame:
    """
    Pad the start and end of the dataframe with np.nan
    :param expected_start: timestamp indicating start time of the data to pad from
    :param expected_end: timestamp indicating end time of the data to pad from
    :param data_df: dataframe with timestamps as column "timestamps"
    :param sample_interval_s: constant sample interval in seconds
    :return: dataframe padded with np.nans in front and back to meet full size of expected start and end
    """
    # extract the necessary information to pad the data
    data_time_stamps = data_df.sort_values("timestamps")["timestamps"].to_numpy()
    first_data_timestamp = data_time_stamps[0]
    last_data_timestamp = data_time_stamps[-1]
    result_df = data_df.copy()
    # FRONT/END GAP FILL!  calculate the audio samples missing based on inputs
    if expected_start < first_data_timestamp:
        start_diff = first_data_timestamp - expected_start
        num_missing_samples = int(dtu.microseconds_to_seconds(start_diff) / sample_interval_s) + 1
        # add the gap data to the result dataframe
        result_df = result_df.append(create_empty_df(expected_start -
                                                     dtu.seconds_to_microseconds(sample_interval_s),
                                                     sample_interval_s, data_df.columns,
                                                     num_missing_samples), ignore_index=True)
    if expected_end > last_data_timestamp:
        last_diff = expected_end - last_data_timestamp
        num_missing_samples = int(dtu.microseconds_to_seconds(last_diff) / sample_interval_s) + 1
        # add the gap data to the result dataframe
        result_df = result_df.append(create_empty_df(expected_end +
                                                     dtu.seconds_to_microseconds(sample_interval_s),
                                                     sample_interval_s, data_df.columns,
                                                     num_missing_samples, True), ignore_index=True)
    return result_df.sort_values("timestamps", ignore_index=True)


def gap_filler(data_df: pd.DataFrame, sample_interval_s: float,
               gap_duration_s: float = DEFAULT_GAP_TIME_S) -> pd.DataFrame:
    """
    fills gaps in the dataframe with np.nan by interpolating timestamps based on the mean expected sample interval
    :param data_df: dataframe with timestamps as column "timestamps"
    :param sample_interval_s: sample interval in seconds
    :param gap_duration_s: duration in seconds of minimum missing data to be considered a gap
    :return: dataframe without gaps
    """
    # extract the necessary information to compute gap size and gap timestamps
    data_time_stamps = data_df.sort_values("timestamps", ignore_index=True)["timestamps"].to_numpy()
    first_data_timestamp = data_time_stamps[0]
    last_data_timestamp = data_time_stamps[-1]
    data_duration_s = dtu.microseconds_to_seconds(last_data_timestamp - first_data_timestamp)
    num_points = len(data_time_stamps)
    # add one to calculation to include the last timestamp
    expected_num_points = int(data_duration_s / sample_interval_s) + 1
    # gap duration cannot be less than sample interval
    if gap_duration_s < sample_interval_s:
        gap_duration_s = sample_interval_s
    result_df = data_df.copy()
    # if there are less points than our expected amount, we have gaps to fill
    if num_points < expected_num_points:
        # if the data we're looking at is short enough, we can start comparing points
        if num_points < 1000:
            # look at every timestamp except the last one
            for index in range(0, num_points - 1):
                # compare that timestamp to the next
                time_diff = dtu.microseconds_to_seconds(data_time_stamps[index + 1] - data_time_stamps[index])
                # calc samples to add, subtracting 1 to prevent copying last timestamp
                num_new_samples = int(time_diff / sample_interval_s) - 1
                if time_diff > gap_duration_s and num_new_samples > 0:
                    # add the gap data to the result dataframe
                    result_df = result_df.append(create_empty_df(data_time_stamps[index], sample_interval_s,
                                                                 data_df.columns, num_new_samples), ignore_index=True)
        else:
            # too many points to check, divide and conquer using recursion!
            half_samples = int(num_points / 2)
            first_data_df = data_df.iloc[:half_samples].copy().reset_index(drop=True)
            second_data_df = data_df.iloc[half_samples:].copy().reset_index(drop=True)
            # give half the samples to each recursive call
            first_data_df = gap_filler(first_data_df, sample_interval_s, gap_duration_s)
            second_data_df = gap_filler(second_data_df, sample_interval_s, gap_duration_s)
            result_df = first_data_df.append(second_data_df, ignore_index=True)
    return result_df.sort_values("timestamps", ignore_index=True)


def create_empty_df(start_timestamp: float, sample_interval_s: float, columns: pd.Index,
                    num_samples_to_add: int, add_to_start: bool = False) -> pd.DataFrame:
    """
    Creates an empty dataframe with num_samples_to_add - 1 timestamps, using columns as the columns
    The one timestamp not being added would be a copy of the start timestamp.
    :param start_timestamp: timestamp to start calculating other timestamps from
    :param sample_interval_s: fixed sample interval in seconds
    :param columns: the non-timestamp columns of the dataframe
    :param num_samples_to_add: the number of timestamps to create
    :param add_to_start: if True, subtracts sample_interval_s from start_timestamp, default False
    :return:
    """
    if add_to_start:
        sample_interval_s = -sample_interval_s
    new_timestamps = np.vectorize(lambda t: start_timestamp + dtu.seconds_to_microseconds(t * sample_interval_s))(
        list(range(1, num_samples_to_add + 1)))
    empty_df = pd.DataFrame([], columns=columns)
    for column_index in columns:
        if column_index == "timestamps":
            empty_df["timestamps"] = new_timestamps
        else:
            empty_df[column_index] = np.nan
    # return a dataframe with only timestamps
    return empty_df
