from typing import Union
from historical_data_feeds.modules.data_source_base import DataSource
from datetime import datetime
from libs.interfaces.historical_data_feeds.instrument_file import InstrumentFile
from libs.interfaces.utils.data_symbol import DataSymbol
from os import getenv
from libs.utils.singleton import singleton
# from historical_data_feeds.modules.utils import validate_dataframe_timestamps

@singleton
class RB30DataSource(DataSource):
    def __init__(self, logger=print):
        super().__init__(False, logger)

    def _get_interval_miliseconds(self, interval: str) -> Union[int,None]: 
        pass

    async def _validate_instrument_data(self, data: DataSymbol) -> bool:
        return True

    async def _download_instrument_data(self, 
                        downloaded_data_path: str, 
                        instrument_file: InstrumentFile):
        return True
