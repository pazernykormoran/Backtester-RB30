
from abc import abstractmethod
import asyncio
from typing import List
from libs.interfaces.python_backtester.data_finish import DataFinish as DataFinishBacktester
from libs.interfaces.python_engine.custom_chart_element import CustomChartElement
from libs.interfaces.python_engine.data_finish import DataFinish as DataFinishEngine
from libs.zmq.zmq import ZMQ
from libs.list_of_services.list_of_services import SERVICES
import pandas as pd
from libs.data_feeds.data_feeds import DataSchema
from importlib import import_module
from libs.interfaces.utils import JSONSerializable


class Engine(ZMQ):
    # override

    def __init__(self, config: dict, logger=print):
        super().__init__(config, logger)
        self.__data_schema: DataSchema = import_module('strategies.'+self.config.strategy_name+'.data_schema').DATA
        self.__columns=['timestamp']+[c.symbol for c in self.__data_schema.data]
        self.__data_buffer_dict = [ [] for col in self.__columns]

        self.__data_buffer_pandas = pd.DataFrame(columns=self.__columns)
        self.__data_buffer = []
        self.__buffer_length = 100
        self.__custom_charts = []

        self.register("data_feed", self.__data_feed_event_3)
        self.register("historical_sending_locked", self.__historical_sending_locked_event)
        self.register("data_finish", self.__data_finish_event)

    @abstractmethod
    def on_feed(self, data):
        pass

    def on_data_finish(self):
        pass

    # override
    def _loop(self):
        loop = asyncio.get_event_loop()
        # loop.create_task(self._listen_zmq())
        self._create_listeners(loop)
        loop.create_task(self.__some_loop())
        loop.run_forever()
        loop.close()

    async def __some_loop(self):
        while True:
            await asyncio.sleep(2)
            # self._log('somethind')

    # override
    def _handle_zmq_message(self, message):
        pass

    def _get_columns(self):
        return self.__columns

    def _set_buffer_length(self, length: int):
        self.__buffer_length = length

    def _trigger_event(self, event: JSONSerializable):
        msg = {
            'price': self.__get_main_intrument_price_3(),
            'timestamp': self.__data_buffer_dict[0][-1],
            'message': event
        }
        self._send(SERVICES.python_executor,'event', msg)

    def _get_main_intrument_number(self):
        num = [i for i, v in enumerate(self.__data_schema.data) if v.main == True][0]
        return num + 1
    
    def _add_custom_chart(self, chart: List[CustomChartElement], name: str, display_on_price_chart: bool = False):
        chart_obj = {
            'chart': chart,
            'display_on_price_chart': display_on_price_chart,
            'name': name
        }
        self.__custom_charts.append(chart_obj)

    def __get_main_intrument_price(self):
         # first function
        num = [i for i, v in enumerate(self.__data_schema.data) if v.main == True][0]
        return self.__data_buffer[-1][num+1]

    def __get_main_intrument_price_2(self):
        num = [i for i, v in enumerate(self.__data_schema.data) if v.main == True][0]
        return self.__data_buffer_pandas.iloc[-1, num+1]

    def __get_main_intrument_price_3(self, price_delay_steps = -1):
        num = [i for i, v in enumerate(self.__data_schema.data) if v.main == True][0]
        return self.__data_buffer_dict[num+1][price_delay_steps]

    #COMMANDS
    def __data_feed_event_2(self, new_data_row):
        # using this function everythink runs 10 time slower.
        if self.__data_buffer_pandas.shape[0]>self.__buffer_length:
            self.__data_buffer_pandas.drop(self.__data_buffer_pandas.head(1).index,inplace=True)
        new_data_df = pd.DataFrame([new_data_row], columns=self.__columns)
        # print('shape of new df, ', new_data_df.shape)
        self.__data_buffer_pandas = pd.concat([self.__data_buffer_pandas, new_data_df])
        self.on_feed(self.__data_buffer_pandas)


    def __data_feed_event_3(self, new_data_row):
        for i, v in enumerate(new_data_row):
            self.__data_buffer_dict[i].append(v)
        if len(self.__data_buffer_dict[0])>self.__buffer_length:
            for i, v in enumerate(new_data_row):
                self.__data_buffer_dict[i].pop(0)
            self.on_feed(self.__data_buffer_dict)


    def __data_feed_event(self, new_data_row):
        self.__data_buffer.append(new_data_row)
        if len(self.__data_buffer)>self.__buffer_length:
            self.__data_buffer.pop(0)
            self.on_feed(self.__data_buffer)
        
        
    def __historical_sending_locked_event(self):
        self._send(SERVICES.historical_data_feeds,'unlock_historical_sending')

    def __prepare_custom_charts_to_send(self, custom_charts_list):
        for custom_chart in custom_charts_list:
            custom_chart['chart'] = [[ch.timestamp, ch.value] for ch in custom_chart['chart'] ]
        return custom_charts_list
    
    def __data_finish_event(self, finish_params):
        finish_params = DataFinishEngine(**finish_params)
        finish_params = dict(finish_params)
        self.on_data_finish()
        finish_params['custom_charts'] = self.__prepare_custom_charts_to_send(self.__custom_charts) 
        if len(self.__data_buffer_dict[0]) == 0: 
            self._log('No data has received')
            finish_params['main_instrument_price'] = 0
        else:
            finish_params['main_instrument_price'] = self.__get_main_intrument_price_3()
        
        self._send(SERVICES.python_backtester, 'data_finish', DataFinishBacktester(**finish_params))