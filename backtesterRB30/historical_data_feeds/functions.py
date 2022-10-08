from backtesterRB30.libs.interfaces.historical_data_feeds.instrument_file import InstrumentFile
from backtesterRB30.libs.interfaces.utils.data_symbol import DataSymbol
from backtesterRB30.libs.interfaces.utils.data_schema import DataSchema
from backtesterRB30.libs.interfaces.utils.data_symbol import DataSymbol
from backtesterRB30.libs.data_sources.data_source_base import DataSource
from backtesterRB30.libs.data_sources.data_sources_list import HISTORICAL_SOURCES
from os import listdir
from os.path import isfile, join
from typing import List
from datetime import datetime
import pandas as pd

def synchronize_dataframes(list_of_dfs: List[dict], last_row: list) -> List[list]:
    rows = []
    c = 0
    while True:
        c += 1
        row = [] 
        feeding_next_timestamps = [df['actual_raw'][0] for df in list_of_dfs if df['trigger_feed'] == True and not df['consumed']]
        if len(feeding_next_timestamps) == 0:
            break
        min_timestamp = min(feeding_next_timestamps) 
        row.append(int(min_timestamp))
        for df_obj in list_of_dfs:
            while True:
                if df_obj['actual_raw'][0] > min_timestamp:
                    row.append(df_obj['prev_raw'][1])
                    break
                elif df_obj['actual_raw'][0] == min_timestamp:
                    row.append(df_obj['actual_raw'][1])
                    try:
                        df_obj['prev_raw'] = df_obj['actual_raw']
                        i, v = next(df_obj['rows_iterator'])
                        df_obj['actual_raw'] = list(v)
                    except StopIteration:
                        df_obj['consumed'] = True
                    break
                else: 
                    try:
                        df_obj['prev_raw'] = df_obj['actual_raw']
                        i, v = next(df_obj['rows_iterator'])
                        df_obj['actual_raw'] = list(v)
                    except StopIteration:
                        row.append(df_obj['actual_raw'][1])
                        df_obj['consumed'] = True
                        break
        if len(last_row) == 0 or row[0] != last_row[0]:
            rows.append(row)
            # print(row)
    return rows


def get_instrument_files(symbol: DataSymbol) -> List[str]:
    instrument_files: List[InstrumentFile] = []
    params_touple = (symbol.historical_data_source, symbol.symbol, symbol.interval)

    if symbol.backtest_date_start.year < symbol.backtest_date_stop.year:
        instrument_files.append(InstrumentFile.from_params(
                    *params_touple,
                    symbol.backtest_date_start,
                    datetime(symbol.backtest_date_start.year+1,1,1)))

        for i in range(symbol.backtest_date_stop.year - symbol.backtest_date_start.year - 1):
            instrument_files.append(InstrumentFile.from_params(
                        *params_touple,
                        datetime(symbol.backtest_date_start.year + i + 1, 1, 1),
                        datetime(symbol.backtest_date_start.year + i + 2, 1, 1)))
        
        instrument_files.append(InstrumentFile.from_params(
                    *params_touple,
                    datetime(symbol.backtest_date_stop.year,1,1),
                    symbol.backtest_date_stop))
    else:
        instrument_files.append(InstrumentFile.from_params(
                    *params_touple,
                    symbol.backtest_date_start,
                    symbol.backtest_date_stop))
    return instrument_files

def create_downloading_clients(historical_sources_array: list, data_schema: DataSchema, data_sources: dict, log = print):
    for source in historical_sources_array:
        if source in [data.historical_data_source for data in data_schema.data if \
                data.additional_properties['files_to_download'] != []]:
            data_sources[source]: DataSource = getattr(HISTORICAL_SOURCES, source)(log)

def check_symbol_data_exists(data_symbol: DataSymbol, downloaded_data_path:str ) -> List[InstrumentFile]:
    """
    data scheme
    <symbol>__<source>__<interval>__<date-from>__<date-to>
    all instruments are downloaded in year files.
    """
    files: List[InstrumentFile] = get_instrument_files(data_symbol)
    # self._log('files to download "'+str(data_symbol.symbol)+'" :', files)
    files_in_directory = [f for f in listdir(downloaded_data_path) if isfile(join(downloaded_data_path, f))]
    files_to_download = list(set([f.to_filename() for f in files]) - set(files_in_directory))
    files_to_download = [InstrumentFile.from_filename(file) for file in files_to_download]
    return files_to_download

def map_raw_to_instruments(raw: list, instruments: list):
    last_raw_obj = {}
    if len(raw) != len(instruments):
        print('raw', raw, 'iinstruments', instruments)
        raise Exception('Error in map_raw_to_instruments. Lengths of raw and list of instruments are not equal')
    for value, instrument in zip(raw, instruments):
        last_raw_obj[instrument] = value
    return last_raw_obj


def prepare_dataframes_to_synchronize_2(data_schema: DataSchema, all_columns: list, downloaded_data_path: str, 
                last_row: list, files_array: List[InstrumentFile]) -> List[dict]:
    list_of_dfs = []
    for data_element in data_schema.data:
        columns = ['timestamp', data_element.symbol]
        file_name = 'none'
        actual_raw = [0,0]
        prev_raw = [0,0]
        for element in files_array:
            if data_element.symbol == element.instrument:
                file_name = element.to_filename()
        if file_name == 'none':
            # No file in this period for this instrument. Set empty dataframe.
            df = pd.DataFrame([], columns=columns)
        else:
            # File exists. Load dataframe.
            df = pd.read_csv(join(downloaded_data_path, file_name), index_col=None, header=None, names=columns)
            # append last raw it if exists
            if last_row != []:
                # self._log('appending last row')
                last_raw_mapped = map_raw_to_instruments(last_row, all_columns)
                prev_raw[0] = last_raw_mapped["timestamp"]
                prev_raw[1] = last_raw_mapped[data_element.symbol]
        obj = {
            "trigger_feed": data_element.trigger_feed,
            "rows_iterator": df.iterrows(),
            "actual_raw": actual_raw,
            "prev_raw": prev_raw,
            "consumed": False
        }            
        #prepare to load:
        if obj['actual_raw'][0] == 0:
            try:
                i, v = next(obj['rows_iterator'])
                obj['actual_raw'] = list(v)
            except StopIteration:
                obj['consumed'] = True
        list_of_dfs.append(obj)
    return list_of_dfs
            

def load_data_frame_ticks_2(data_schema: DataSchema, columns: list, \
        downloaded_data_path: str, last_row: list, files_array: List[InstrumentFile]) -> List[list]:
    """
    Function is geting files array from one period that are going to be loaded. 
    Function returns synchronized data in list of lists which are ready to send to engine.
    """
    list_of_dfs = prepare_dataframes_to_synchronize_2(data_schema, columns, downloaded_data_path, last_row, files_array)
    rows = synchronize_dataframes(list_of_dfs, last_row)
    return rows