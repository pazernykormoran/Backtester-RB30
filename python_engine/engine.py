
from abc import abstractmethod
import asyncio
from typing import List, Union
from libs.interfaces.python_backtester.custom_chart import CustomChart
from libs.interfaces.python_backtester.data_finish import DataFinish 
from libs.interfaces.python_backtester.debug_breakpoint import DebugBreakpoint 
from libs.interfaces.python_engine.custom_chart_element import CustomChartElement
from libs.zmq.zmq import ZMQ
from libs.list_of_services.list_of_services import SERVICES
import pandas as pd
from libs.data_feeds.data_feeds import DataSchema
from importlib import import_module, reload
from libs.interfaces.utils import JSONSerializable
import keyboard


class Engine(ZMQ):
    def __init__(self, config: dict, logger=print):
        super().__init__(config, logger)
        self.__data_schema: DataSchema = import_module('strategies.'+self.config.strategy_name+'.data_schema').DATA
        self.__columns=['timestamp']+[c.symbol for c in self.__data_schema.data]
        self.__data_buffer_dict = [ [] for col in self.__columns]

        self.__buffer_length = 100
        self.__custom_charts: List[CustomChart] = []
        self.__debug_mode = False
        self.__debug_next_pressed = False
        self.__reloading_modules = []
        self.__send_breakpoint_after_feed = False
        self.__backtest_finished = False

        super()._register("data_feed", self.__data_feed_event)
        super()._register("historical_sending_locked", self.__historical_sending_locked_event)
        super()._register("data_finish", self.__data_finish_event)

    # public methods:
    # ==================================================================

    @abstractmethod
    async def on_feed(self, data):
        pass


    def on_data_finish(self):
        pass


    def _get_columns(self):
        """
        Function return column names of data_schema.
        """
        return self.__columns


    def _set_buffer_length(self, length: int):
        self.__buffer_length = length


    def _trigger_event(self, event: JSONSerializable):
        """
        Function sends custom message to trade executor service.
        """
        msg = {
            'price': self.__get_main_intrument_price(),
            'timestamp': self.__data_buffer_dict[0][-1],
            'message': event
        }
        super()._send(SERVICES.python_executor,'event', msg)


    def _get_main_intrument_number(self):
        num = [i for i, v in enumerate(self.__data_schema.data) if v.main == True][0]
        return num + 1
    

    def _add_custom_chart(self, 
                    chart: List[CustomChartElement], 
                    name: str, 
                    display_on_price_chart: Union[bool, None] = None, 
                    log_scale: Union[bool, None] = None, 
                    color: Union[str, None] = None):
        """
        Function allows adding custom chart to your strategy.
        Function gets:
            - display_on_price_chart: variable indicates if chart should be displayed
                in the main chart with prices
            - log_scale: variable indicates if chart should be in the log scale. 
                Skipped if display_on_price_chart is true because information about this chart is 
                set in data_schema file
            - color: color of matplotlib chart for example 'red', 'blue' ..
        """
        chart_obj = {
            'chart': chart,
            'display_on_price_chart': display_on_price_chart,
            'name': name
        }
        if display_on_price_chart: chart_obj['display_on_price_chart'] = display_on_price_chart
        if log_scale: chart_obj['log_scale'] = log_scale
        if color: chart_obj['color'] = color
        self.__custom_charts.append(chart_obj)

    
    async def _debug_breakpoint(self):
        """
        Function causes breakpoint if debug mode is turned on.
        """
        if self.__debug_mode == True:
            # reload live modules
            while True:
                if self.__debug_mode == False:
                    for module in self.__reloading_modules:
                        reload(module)
                    return
                if self.__debug_next_pressed == True:
                    for module in self.__reloading_modules:
                        reload(module)
                    self.__debug_next_pressed = False
                    self.__send_breakpoint_after_feed = True
                    return 
                await asyncio.sleep(0.1)


    def _add_reloading_module(self, module: str):
        """
            Function gets path to module
            Function returning added module
        """
        module = import_module(module)
        self.__reloading_modules.append(module)
        return module

    # ==================================================================
    # end of public methods
    

    #private methods:

    def _send(): pass
    def _register(): pass
    def _create_listeners(): pass


    # override
    def _loop(self):
        loop = asyncio.get_event_loop()
        super()._create_listeners(loop)
        loop.create_task(self.__keyboard_listener())
        loop.run_forever()
        loop.close()


    # override
    def _handle_zmq_message(self, message):
        pass


    def __send_debug_breakpoint(self):
        breakpoint_params= {}
        breakpoint_params['last_timestamp'] = self.__data_buffer_dict[0][-1]
        breakpoint_params['main_instrument_price'] = self.__get_main_intrument_price()
        breakpoint_params['custom_charts'] = self.__custom_charts
        self._log('sending debug breakpoint')
        super()._send(SERVICES.python_executor,'debug_breakpoint', DebugBreakpoint(**breakpoint_params))

    def __get_main_intrument_price(self, price_delay_steps = -1):
        if len(self.__data_buffer_dict[0]) == 0: 
            self._log('No data has yet received.')
            return 0
        num = [i for i, v in enumerate(self.__data_schema.data) if v.main == True][0]
        return self.__data_buffer_dict[num+1][price_delay_steps]


    async def __keyboard_listener(self):
        self._log('To enter debug mode press "d"')
        while True:
            if keyboard.is_pressed('d'): 
                if self.__debug_mode == False:
                    self._log('You have entered Debug mode \n\
                                 -> press "n" to next step\n\
                                 -> press "q" to leave debug mode')
                    self.__debug_mode = True
                while keyboard.is_pressed('d'):
                    await asyncio.sleep(0.1)
            if keyboard.is_pressed('n'):
                if self.__debug_mode == True and self.__debug_next_pressed == False:
                    self._log('next step ... \n\
                                -> press "q" to leave debug mode')
                    self.__debug_next_pressed = True
                while keyboard.is_pressed('n'):
                    await asyncio.sleep(0.1)
            if keyboard.is_pressed('q'):
                if self.__debug_mode == True:
                    self._log('You have leaved Debug mode \n\
                                -> press "d" to enter debug mode again')
                    self.__debug_mode = False
                while keyboard.is_pressed('q'):
                    await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)


    #COMMANDS

    async def __data_feed_event(self, new_data_row):
        for i, v in enumerate(new_data_row):
            self.__data_buffer_dict[i].append(v)
        if len(self.__data_buffer_dict[0])>self.__buffer_length:
            for i, v in enumerate(new_data_row):
                self.__data_buffer_dict[i].pop(0)
            await self.on_feed(self.__data_buffer_dict)
            if self.__send_breakpoint_after_feed: 
                self.__send_debug_breakpoint()
                self.__send_breakpoint_after_feed = False
        
        
    async def __historical_sending_locked_event(self):
        super()._send(SERVICES.historical_data_feeds,'unlock_historical_sending')

    
    async def __data_finish_event(self):
        self.on_data_finish()
        self.__debug_mode = False
        self.__backtest_finished = True
        finish_params = {}
        finish_params['custom_charts'] = self.__custom_charts
        finish_params['main_instrument_price'] = self.__get_main_intrument_price()
        super()._send(SERVICES.python_backtester, 'data_finish', DataFinish(**finish_params))
