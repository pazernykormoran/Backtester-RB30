from datetime import datetime
from json import load
from os import system, remove, walk
from os.path import join
import shutil
from typing import Union
import pandas as pd
from backtesterRB30.historical_data_feeds.modules.data_source_base import DataSource
from backtesterRB30.libs.interfaces.historical_data_feeds.instrument_file import InstrumentFile
from backtesterRB30.libs.interfaces.utils.data_symbol import DataSymbol
from os import getenv, getcwd
from backtesterRB30.libs.utils.singleton import singleton
import importlib.resources
import json

# from backtesterRB30.historical_data_feeds.modules.utils import validate_dataframe_timestamps

@singleton
class DukascopyDataSource(DataSource):
    def __init__(self, logger=print):
        super().__init__(False, logger)

    def __get_ducascopy_interval(self, interval: str) -> str:
        if interval == 'tick': return 'tick'
        if interval == 'minute': return 'm1'
        if interval == 'minute5': return 'm5'
        if interval == 'minute15': return 'm15'
        if interval == 'minute30': return 'm30'
        if interval == 'hour': return 'h1'
        if interval == 'day': return 'd1'
        if interval == 'month': return 'mn1'

    def _get_interval_miliseconds(self, interval: str) -> Union[int,None]: 
        if interval == 'tick': return None
        if interval == 'minute': return 60*1000
        if interval == 'minute5': return 5*60*1000
        if interval == 'minute15': return 15*60*1000
        if interval == 'minute30': return 30*60*1000
        if interval == 'hour': return 60*60*1000
        if interval == 'day': return 24*60*60*1000
        if interval == 'month': return None


    async def _validate_instrument_data(self, data: DataSymbol) -> bool:
        # https://raw.githubusercontent.com/Leo4815162342/dukascopy-node/master/src/utils/instrument-meta-data/generated/raw-meta-data-2022-04-23.json
        # response = requests.get("http://api.open-notify.org/astros.json")
        from_datetime_timestamp = int(round(datetime.timestamp(data.backtest_date_start) * 1000))
        # f = open('temporary_ducascopy_list.json')
        # instrument_list = load(f)['instruments']
        with importlib.resources.open_text("backtesterRB30", "temporary_ducascopy_list.json") as file:
            instrument_list = json.load(file)['instruments']
        #validate if instrument exists:
        if data.symbol.upper() not in [v['historical_filename'] for k, v in instrument_list.items()]:
            self._log('Error. Instrument "'+data.symbol+'" does not exists on ducascopy.')
            return False

        #validate it timestamps perios is right:
        for k, v in instrument_list.items():
            if v["historical_filename"] == data.symbol.upper():
                first_timestamp = int(v["history_start_day"])
                if first_timestamp > from_datetime_timestamp:
                    print("Error. First avaliable date of " , data.symbol, "is" , datetime.fromtimestamp(first_timestamp/1000.0))
                    return False

        return True

    async def _download_instrument_data(self, 
                        downloaded_data_path: str, 
                        instrument_file: InstrumentFile):
        self._log('Downloading dukascopy data', instrument_file.to_filename())
        """
        documentation: 
        https://github.com/Leo4815162342/dukascopy-node
        """

        duca_interval = self.__get_ducascopy_interval(instrument_file.interval)
        from_param = datetime.fromtimestamp(instrument_file.time_start//1000.0).strftime("%Y-%m-%d")
        to_param = datetime.fromtimestamp(instrument_file.time_stop//1000.0).strftime("%Y-%m-%d")
        here = getcwd()
        cache_path = join(here, 'cache_dukascopy')
        system('rm -r ' + cache_path)
        string_params = [
            ' -i '+ instrument_file.instrument,
            ' -from '+ from_param,
            ' -to '+ to_param,
            ' -s',
            ' -t ' + duca_interval,
            ' -fl', 
            ' -f csv',
            ' -dir '+ cache_path,
            ' -p bid'
        ]
        command = 'npx dukascopy-node'
        for param in string_params:
            command += param
        system(command)
        name_of_created_file = next(walk(cache_path), (None, None, []))[2][0]  
        df = pd.read_csv(join(cache_path, name_of_created_file), index_col=None, header=None)
        if duca_interval == 'tick': 
            df = df.iloc[1:, [0,2]]
        else:
            df = df.iloc[1:, [0,1]]
        if name_of_created_file and name_of_created_file != '':
            remove(join(cache_path, name_of_created_file))
        # print('Dukascopy df shape after dl', df.shape)
        # print('head', str(df.head(1)))
        # print('tail', str(df.tail(1)))
        df.to_csv(join(downloaded_data_path, instrument_file.to_filename()), index=False, header=False)
