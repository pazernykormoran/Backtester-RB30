from os import getenv
strategy_name = getenv('STRATEGY_NAME')
# microservice_name = getenv('NAME')
microservice_name = 'python_backtester'
sub_ports = [int(p) for p in getenv(microservice_name+'_subs').split(',')]
pub_ports = [int(p) for p in getenv(microservice_name+'_pubs').split(',')]
backtest_state = getenv('backtest_state')


from python_backtester.python_backtester import Backtester
from libs.interfaces.config import Config
config = {
    "name": microservice_name,
    "ip": "localhost",
    "sub": [
        {
        "topic": microservice_name,
        "port": p
        } for p in sub_ports
    ],
    "pub": [
        {
            "topic": 'pub_'+str(p),
            "port": p
        } for p in pub_ports
    ],
    "backtest": True if backtest_state == 'true' else False,
    "strategy_name": strategy_name
}
service = Backtester(Config(**config))
service.run()